#!/bin/bash
# remote_install.sh - Дистанционная установка/удаление сервиса sPion
#
# Скрипт скачивает installer.py из репозитория sPion, предварительно создаёт на удалённом устройстве папку ~/code/
# и клонирует репозиторий sPion (если он ещё не существует), затем выполняет installer.py с переданными параметрами,
# а затем удаляет скачанный installer.py.
#
# Использование:
#   ./remote_install.sh --ssh_host <IP> --ssh_user <user> --ssh_password <password> [--install|--remove]
#
# Пример вызова:
# sudo curl -sSL https://raw.githubusercontent.com/OnisOris/sPion/refs/heads/main/install_service.sh | sudo bash -s -- --ssh_host 192.168.137.57 --ssh_user pi --ssh_password raspberry --install

set -e

# Парсинг параметров
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --ssh_host) SSH_HOST="$2"; shift ;;
        --ssh_user) SSH_USER="$2"; shift ;;
        --ssh_password) SSH_PASSWORD="$2"; shift ;;
        --install) ACTION="install" ;;
        --remove) ACTION="remove" ;;
        *) echo "Неизвестный параметр: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$SSH_HOST" ] || [ -z "$SSH_USER" ] || [ -z "$ACTION" ]; then
    echo "Использование: $0 --ssh_host <IP> --ssh_user <user> [--ssh_password <password>] [--install|--remove]"
    exit 1
fi

echo "Создание директории ~/code/ и клонирование репозитория sPion на удалённом устройстве..."
if [ -n "$SSH_PASSWORD" ]; then
    sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no "$SSH_USER@$SSH_HOST" \
    "mkdir -p ~/code && cd ~/code && if [ ! -d sPion ]; then git clone https://github.com/OnisOris/sPion.git; fi"
else
    ssh "$SSH_USER@$SSH_HOST" "mkdir -p ~/code && cd ~/code && if [ ! -d sPion ]; then git clone https://github.com/OnisOris/sPion.git; fi"
fi

echo "Скачивание installer.py из репозитория..."
curl -sSL "https://raw.githubusercontent.com/OnisOris/sPion/refs/heads/main/scripts/remote_installer/installer.py" -o installer.py

if [ ! -f installer.py ]; then
    echo "Ошибка загрузки installer.py"
    exit 1
fi

echo "Запуск installer.py с параметрами: SSH_HOST=${SSH_HOST}, SSH_USER=${SSH_USER}, ACTION=${ACTION}"
if [ -n "$SSH_PASSWORD" ]; then
    python3 installer.py --ssh_host "$SSH_HOST" --ssh_user "$SSH_USER" --ssh_password "$SSH_PASSWORD" --$ACTION
else
    python3 installer.py --ssh_host "$SSH_HOST" --ssh_user "$SSH_USER" --$ACTION
fi

