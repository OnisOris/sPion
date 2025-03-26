#!/usr/bin/env python3
import time
import argparse
import paramiko
import sys
import shlex
from textwrap import dedent

class RadxaInstaller:
    def __init__(self, ssh_host: str, ssh_user: str, ssh_password: str):
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_password = ssh_password
        self.sudo_password = ssh_password
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        print(f"Connecting to {self.ssh_host} as {self.ssh_user}...")
        self.ssh.connect(
            self.ssh_host,
            username=self.ssh_user,
            password=self.ssh_password,
            timeout=10,
            look_for_keys=False,
            allow_agent=False
        )
        self.transport = self.ssh.get_transport()

    def exec_command(self, cmd, timeout=15):
        """Execute regular command (non-sudo)"""
        print(f"\nExecuting command: {cmd}")
        chan = self.transport.open_session()
        chan.exec_command(cmd)
        exit_code = chan.recv_exit_status()
        
        stdout = chan.makefile('r', -1).read().strip()
        stderr = chan.makefile_stderr('r', -1).read().strip()
        
        # Decode bytes to string if needed
        if isinstance(stdout, bytes):
            stdout = stdout.decode('utf-8', errors='ignore')
        if isinstance(stderr, bytes):
            stderr = stderr.decode('utf-8', errors='ignore')
        
        print(f"Exit code: {exit_code}")
        if stdout:
            print(f"stdout:\n{stdout}")
        if stderr:
            print(f"stderr:\n{stderr}")
        return exit_code, stdout, stderr

    def exec_sudo(self, cmd, timeout=15):
        """Execute command with sudo and password injection"""
        sudo_cmd = f"echo {shlex.quote(self.sudo_password)} | sudo -S {cmd}"
        return self.exec_command(sudo_cmd, timeout)

    def check_service_exists(self):
        """Check if service already installed"""
        exit_code, stdout, _ = self.exec_sudo("systemctl list-unit-files | grep pion_server.service")
        return exit_code == 0 and "pion_server.service" in stdout

    def remove_old_service(self):
        """Remove existing service"""
        print("Removing old service...")
        self.exec_sudo("systemctl stop pion_server || true", timeout=10)
        self.exec_sudo("systemctl disable pion_server || true", timeout=10)
        self.exec_sudo("rm -f /etc/systemd/system/pion_server.service", timeout=10)
        self.exec_sudo("systemctl daemon-reload", timeout=10)

    def install_dependencies(self):
        """Install system dependencies"""
        print("\nInstalling dependencies...")
        cmds = [
            "apt-get update",
            "apt-get install -y python3 python3-pip wget curl git",
            "python3 -m pip install --upgrade pip"
        ]
        for cmd in cmds:
            exit_code, _, _ = self.exec_sudo(cmd, timeout=300)
            if exit_code != 0:
                raise RuntimeError(f"Failed to execute: {cmd}")

    def clone_repo(self):
        """Clone or update repository"""
        print("\nConfiguring repository...")
        cmd = (
            "mkdir -p ~/code && cd ~/code && "
            "(git clone https://github.com/OnisOris/sPion.git || (cd ~/code/sPion && git pull))"
        )
        exit_code, _, _ = self.exec_command(cmd, timeout=60)
        if exit_code != 0:
            raise RuntimeError("Repository configuration failed")

    def setup_virtualenv(self):
        """Create Python virtual environment"""
        print("\nSetting up virtual environment...")
        cmds = [
            "cd ~/code/sPion",
            "python3 -m venv .venv --clear",
            "source .venv/bin/activate && pip install -r requirements.txt"
        ]
        exit_code, _, _ = self.exec_command(" && ".join(cmds), timeout=120)
        if exit_code != 0:
            raise RuntimeError("Virtual environment setup failed")

    def install_pion_dependencies(self):
        """Install Pion specific dependencies"""
        print("\nInstalling Pion dependencies...")
        cmd = "sudo curl -sSL https://raw.githubusercontent.com/OnisOris/pion/refs/heads/dev/scripts/install_linux.sh | sudo bash"
        exit_code, _, _ = self.exec_sudo(cmd, timeout=300)
        if exit_code != 0:
            raise RuntimeError("Pion dependencies installation failed")

    def configure_service(self):
        """Create systemd service file"""
        print("\nConfiguring systemd service...")
        unit_content = dedent(f"""\
        [Unit]
        Description=Pion Server
        After=network-online.target
        Wants=network-online.target

        [Service]
        User={self.ssh_user}
        WorkingDirectory=/home/{self.ssh_user}/code/sPion
        ExecStart=/bin/bash -c 'cd /home/{self.ssh_user}/code/sPion && git pull && source .venv/bin/activate && python3 main.py'
        Restart=always
        RestartSec=10
        StandardOutput=journal
        StandardError=journal

        [Install]
        WantedBy=multi-user.target
        """)
        
        # Write to temporary file and move with sudo
        cmd = f"echo '{unit_content}' > /tmp/pion_server.service && " \
              f"sudo mv /tmp/pion_server.service /etc/systemd/system/ && " \
              f"sudo chmod 644 /etc/systemd/system/pion_server.service"
        
        exit_code, _, _ = self.exec_command(cmd, timeout=20)
        if exit_code != 0:
            raise RuntimeError("Failed to configure service file")

    def enable_service(self):
        """Enable and start service"""
        print("\nActivating service...")
        cmds = [
            "systemctl daemon-reload",
            "systemctl enable pion_server.service",
            "systemctl start pion_server.service"
        ]
        for cmd in cmds:
            exit_code, _, _ = self.exec_sudo(cmd, timeout=20)
            if exit_code != 0:
                raise RuntimeError(f"Failed to execute: {cmd}")

    def install(self):
        try:
            self.connect()
            
            if self.check_service_exists():
                self.remove_old_service()

            self.install_dependencies()
            self.clone_repo()
            self.setup_virtualenv()
            self.install_pion_dependencies()
            self.configure_service()
            self.enable_service()

            print("\nInstallation completed successfully!")
            print("Service status: sudo systemctl status pion_server")

        except Exception as e:
            print(f"\nError: {str(e)}")
            sys.exit(1)
        finally:
            self.ssh.close()
            print("Connection closed.")

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Install Pion service on Radxa')

    parser.add_argument('--ssh-host', '--ssh_host', required=True, dest='ssh_host', help='SSH hostname/IP')
    parser.add_argument('--ssh-user', '--ssh_user', required=True, dest='ssh_user', help='SSH username')
    parser.add_argument('--ssh-password', '--ssh_password', required=True, dest='ssh_password', help='SSH password')

    args = parser.parse_args()
    
    installer = RadxaInstaller(
        ssh_host=args.ssh_host,
        ssh_user=args.ssh_user,
        ssh_password=args.ssh_password
    )
    installer.install()
