#!/usr/bin/env python3
import time
from pion import Pion
from pion.server import SwarmCommunicator

def main():
    # Получаем IP из локальной сети или оставляем 127.0.0.1
    ip = "127.0.0.1"
    drone = Pion(ip=ip, mavlink_port=5656, name=f"Drone-{ip}", dt=0.01, logger=True, max_speed=0.5)
    swarm_comm = SwarmCommunicator(control_object=drone, broadcast_port=37020, broadcast_interval=0.5)
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
