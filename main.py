#!/usr/bin/env python3
import socket
import time
from pion import Pion
from pion.server import SwarmCommunicator

def get_local_ip():
    """
    Получаем локальный IP-адрес, используя временное UDP-соединение.
    Если получить адрес не удалось, возвращаем '127.0.0.1'.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Соединяемся с внешним адресом. Адрес не обязательно должен быть доступен.
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"
    finally:
        s.close()
    return local_ip

def main():
    # Получаем локальный IP-адрес
    ip = get_local_ip()
    drone = Pion(ip="127.0.0.1", mavlink_port=5656, name=f"Drone-{ip}", dt=0.01, logger=True, max_speed=0.5)
    swarm_comm = SwarmCommunicator(control_object=drone, broadcast_port=37020, broadcast_interval=0.5, ip=ip)
    swarm_comm.start()
    print(f"SwarmCommunicator запущен для {drone.name} с IP {ip}")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        swarm_comm.stop()
        print("Swarm communicator остановлен.")

if __name__ == "__main__":
    main()

