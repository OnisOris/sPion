#!/usr/bin/env python3
import time
import argparse
import paramiko
import sys

class RemoteServiceInstaller:
    def __init__(self, ssh_host: str, ssh_user: str, ssh_password: str):
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_password = ssh_password
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        print(f"Подключаемся по SSH к {self.ssh_host} как {self.ssh_user}...")
        self.ssh.connect(self.ssh_host, username=self.ssh_user, password=self.ssh_password, timeout=10)
        self.transport = self.ssh.get_transport()

    def exec_command(self, cmd, timeout=15):
        print(f"\nВыполняется команда: {cmd}")
        chan = self.transport.open_session()
        chan.exec_command(cmd)
        exit_code = chan.recv_exit_status()
        stdout = chan.makefile('r', -1).read().strip()
        stderr = chan.makefile_stderr('r', -1).read().strip()
        print(f"Код завершения: {exit_code}")
        if stdout:
            print(f"stdout:\n{stdout}")
        if stderr:
            print(f"stderr:\n{stderr}")
        return exit_code, stdout, stderr

    def exec_command_with_retry(self, cmd, timeout=15, retries=5, delay=5):
        for attempt in range(1, retries + 1):
            exit_code, stdout, stderr = self.exec_command(cmd, timeout=timeout)
            if exit_code == 0:
                return exit_code, stdout, stderr
            if "lock" in stderr.lower():
                print(f"Обнаружена блокировка dpkg (попытка {attempt}/{retries}). Повтор через {delay} секунд...")
                time.sleep(delay)
            else:
                break
        return exit_code, stdout, stderr

    def install(self):
        try:
            self.connect()
            # Если сервис уже существует – обновляем репозиторий и перезапускаем сервис
            exit_code, stdout, _ = self.exec_command("sudo systemctl list-unit-files | grep pion_server.service")
            if exit_code == 0 and stdout:
                print("Pion server уже установлен. Обновляем репозиторий и перезапускаем сервис.")
                self.exec_command("cd ~/code/sPion && git pull", timeout=30)
                self.restart_service()
                return

            print("\nНачинаем установку Pion server для Raspberry Pi Zero 2W...")

            # Обновляем списки пакетов и устанавливаем apt-зависимости
            exit_code, _, _ = self.exec_command_with_retry(
                "sudo apt-get update && sudo apt-get install -y python3 python3-pip wget curl git",
                timeout=60
            )
            if exit_code != 0:
                raise Exception("Ошибка установки зависимостей через apt-get")

            # Выполняем установку зависимостей Pion (внешний скрипт установки)
            install_cmd = ("sudo curl -sSL https://raw.githubusercontent.com/OnisOris/pion/refs/heads/dev/install_scripts/install_linux.sh | sudo bash")
            exit_code, _, _ = self.exec_command(install_cmd, timeout=60)
            if exit_code != 0:
                raise Exception("Ошибка установки зависимостей Pion")

            # Клонируем или обновляем репозиторий sPion в ~/code/sPion
            clone_cmd = ("mkdir -p ~/code && cd ~/code && "
                         "if [ -d sPion ]; then cd sPion && git pull; else git clone https://github.com/OnisOris/sPion.git; fi")
            exit_code, _, _ = self.exec_command(clone_cmd, timeout=30)
            if exit_code != 0:
                raise Exception("Ошибка клонирования/обновления репозитория sPion")

            # Создаем виртуальное окружение в корне репозитория, если его нет, и устанавливаем зависимости
            venv_cmd = (
                "cd ~/code/sPion && "
                "if [ ! -d .venv ]; then "
                "python3 -m venv .venv && "
                "source .venv/bin/activate && "
                "pip install --upgrade pip && "
                "pip install -r requirements.txt; "
                "else "
                "source .venv/bin/activate && pip install -r requirements.txt; "
                "fi"
            )
            exit_code, _, _ = self.exec_command(venv_cmd, timeout=60)
            if exit_code != 0:
                raise Exception("Ошибка создания виртуального окружения и установки зависимостей")

            # Создаем systemd unit для сервиса с WorkingDirectory = ~/code/sPion
            unit_command = f"""sudo tee /etc/systemd/system/pion_server.service > /dev/null << 'EOF'
[Unit]
Description=Pion Server
After=network.target

[Service]
User={self.ssh_user}
WorkingDirectory=/home/{self.ssh_user}/code/sPion
ExecStart=/bin/bash -c "source /home/{self.ssh_user}/code/sPion/.venv/bin/activate && nohup python3 /home/{self.ssh_user}/code/sPion/main.py >> /home/{self.ssh_user}/code/sPion/pion_server.log 2>&1"
Restart=always
StandardOutput=null
StandardError=null

[Install]
WantedBy=multi-user.target
EOF
"""
            exit_code, _, _ = self.exec_command(unit_command, timeout=15)
            if exit_code != 0:
                raise Exception("Ошибка создания файла сервиса pion_server.service")

            # Перезагружаем конфигурацию systemd и запускаем сервис
            exit_code, _, _ = self.exec_command("sudo systemctl daemon-reload", timeout=15)
            if exit_code != 0:
                raise Exception("Ошибка перезагрузки демона systemd")
            self.exec_command("sudo systemctl unmask pion_server.service", timeout=10)
            exit_code, _, _ = self.exec_command("sudo systemctl enable pion_server.service", timeout=15)
            if exit_code != 0:
                raise Exception("Ошибка включения сервиса pion_server")
            exit_code, _, _ = self.exec_command("sudo systemctl start pion_server.service", timeout=15)
            if exit_code != 0:
                raise Exception("Ошибка запуска сервиса pion_server")

            print("\nPion server успешно установлен и запущен на Raspberry Pi Zero 2W")

        except Exception as e:
            print(f"\nКритическая ошибка: {str(e)}")
            try:
                print("\nСбор логов сервиса pion_server:")
                _, logs, _ = self.ssh.exec_command("journalctl -u pion_server -n 20")
                logs_str = logs.read().decode().strip()
                print("Логи сервиса:\n", logs_str)
            except Exception as inner_e:
                print("Не удалось получить логи:", inner_e)
            sys.exit(1)
        finally:
            self.ssh.close()
            print("SSH-соединение закрыто.")

    def restart_service(self):
        # Обновляем репозиторий и перезапускаем сервис
        self.exec_command("cd ~/code/sPion && git pull", timeout=30)
        self.exec_command("sudo systemctl restart pion_server.service", timeout=15)
        print("Сервис успешно перезапущен.")


class RemoteServiceRemover:
    def __init__(self, ssh_host: str, ssh_user: str, ssh_password: str):
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_password = ssh_password
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        print(f"Подключаемся по SSH к {self.ssh_host} для удаления сервиса pion_server...")
        self.ssh.connect(self.ssh_host, username=self.ssh_user, password=self.ssh_password, timeout=10)
        self.transport = self.ssh.get_transport()

    def exec_command(self, cmd, timeout=15):
        print(f"\nВыполняется команда: {cmd}")
        chan = self.transport.open_session()
        chan.exec_command(cmd)
        exit_code = chan.recv_exit_status()
        stdout = chan.makefile('r', -1).read().strip()
        stderr = chan.makefile_stderr('r', -1).read().strip()
        print(f"Код завершения: {exit_code}")
        if stdout:
            print(f"stdout:\n{stdout}")
        if stderr:
            print(f"stderr:\n{stderr}")
        return exit_code, stdout, stderr

    def remove(self):
        try:
            self.connect()
            # Останавливаем сервис, если он запущен
            self.exec_command("sudo systemctl stop pion_server")
            # Отключаем автозапуск
            self.exec_command("sudo systemctl disable pion_server")
            # Удаляем unit-файл
            self.exec_command("sudo rm -f /etc/systemd/system/pion_server.service")
            # Обновляем конфигурацию systemd
            self.exec_command("sudo systemctl daemon-reload")
            print("\nСервис pion_server успешно удалён. Теперь можно провести тест установки.")
        except Exception as e:
            print(f"\nОшибка при удалении сервиса: {str(e)}")
        finally:
            self.ssh.close()
            print("SSH-соединение закрыто.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Установка или удаление Pion сервиса на удалённом устройстве")
    parser.add_argument("--ssh_host", required=True, help="IP или доменное имя удалённого устройства")
    parser.add_argument("--ssh_user", required=True, help="Пользователь SSH")
    parser.add_argument("--ssh_password", required=True, help="Пароль SSH")
    parser.add_argument("--install", action="store_true", help="Установить/обновить сервис")
    parser.add_argument("--remove", action="store_true", help="Удалить сервис")
    args = parser.parse_args()

    if args.remove:
        remover = RemoteServiceRemover(args.ssh_host, args.ssh_user, args.ssh_password)
        remover.remove()

    if args.install:
        installer = RemoteServiceInstaller(args.ssh_host, args.ssh_user, args.ssh_password)
        installer.install()
    elif not args.remove:
        print("Укажите либо --install, либо --remove")
        sys.exit(1)
