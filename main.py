#!/usr/bin/env python3
import socket
import time
from pion import Pion
from pion.server import SwarmCommunicator
from typing import Any, Optional

class Swarmc(SwarmCommunicator):
    def __init__(self,
                 control_object: Any,
                 broadcast_port: int = 37020, 
                 broadcast_interval: float = 0.05,
                 safety_radius: float = 1.,
                 max_speed: float = 1.,
                 ip = None,
                 instance_number = None,
                 time_sleep_update_velocity: float = 0.1,
                 params: Optional[dict] = None):
        SwarmCommunicator.__init__(self,
                 control_object = control_object,
                 broadcast_port = broadcast_port, 
                 broadcast_interval = broadcast_interval,
                 safety_radius = safety_radius,
                 max_speed = max_speed,
                 ip = ip,
                 instance_number = instance_number,
                 time_sleep_update_velocity = time_sleep_update_velocity,
                 params = params)

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
    drone = Pion(ip='/dev/ttyS0',
                 mavlink_port=230400,
                 connection_method='serial',
                 name=f"Drone-{ip}",
                 dt=0.001,
                 logger=True,
                 max_speed=0.5)
    params = {
                "attraction_weight": 1.0,
                "cohesion_weight": 1.0,
                "alignment_weight": 1.0,
                "repulsion_weight": 4.0,
                "unstable_weight": 1.0,
                "noise_weight": 1.0,
                "safety_radius": 1.0,
                "max_acceleration": 1,
                "max_speed": 0.6,
            }
    swarm_comm = Swarmc(control_object=drone,
                                   broadcast_port=37020,
                                   broadcast_interval=0.5,
                                   ip=ip,
                                   time_sleep_update_velocity = 0.05,
                                   params=params)
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

