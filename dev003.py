#!/usr/bin/env python3
"""
Скрипт для выключения света во всем здании через центральный IoT-контроллер
Предназначен для систем типа: KNX, Modbus, BACnet, DALI, OPC UA
"""

import requests
import socket
import json
import time
from typing import Dict, List, Optional

class BuildingLightController:
    def __init__(self):
        # Протоколы и порты для систем управления зданием
        self.building_protocols = {
            'knx': {'port': 3671, 'protocol': 'UDP'},
            'modbus': {'port': 502, 'protocol': 'TCP'},
            'bacnet': {'port': 47808, 'protocol': 'UDP'},
            'dali': {'port': 50000, 'protocol': 'TCP'},
            'opcua': {'port': 4840, 'protocol': 'TCP'},
            'rest_api': {'port': 80, 'protocol': 'HTTP'},
            'mqtt': {'port': 1883, 'protocol': 'TCP'}
        }
        
        # IP адреса возможных контроллеров в сети здания
        self.common_controllers = [
            '192.168.1.100',  # Основной контроллер
            '192.168.1.101',  # Резервный контроллер
            '192.168.1.200',  # Шлюз KNX/IP
            '192.168.1.201',  # Modbus TCP шлюз
            '192.168.1.10',   # Сервер OPC UA
            '192.168.1.50',   # BACnet IP устройство
            'plc.local',      # Локальное имя PLC
            'building-ctrl.local'
        ]

    def discover_building_controllers(self) -> List[Dict]:
        """Обнаружение контроллеров управления зданием"""
        print("🔍 Поиск контроллеров управления зданием...")
        
        found_controllers = []
        
        for controller_ip in self.common_controllers:
            for protocol_name, protocol_info in self.building_protocols.items():
                if self.check_controller(controller_ip, protocol_info['port'], protocol_info['protocol']):
                    found_controllers.append({
                        'ip': controller_ip,
                        'port': protocol_info['port'],
                        'protocol': protocol_name,
                        'type': protocol_info['protocol']
                    })
                    print(f"✅ Найден {protocol_name.upper()} контроллер: {controller_ip}:{protocol_info['port']}")
        
        return found_controllers

    def check_controller(self, ip: str, port: int, protocol: str) -> bool:
        """Проверка доступности контроллера"""
        try:
            if protocol in ['TCP', 'HTTP']:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((ip, port))
                sock.close()
                return result == 0
            elif protocol == 'UDP':
                # Для UDP отправляем пробный пакет
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(2)
                sock.sendto(b'\x00', (ip, port))
                sock.close()
                return True
        except:
            return False
        return False

    def turn_off_lights_via_rest(self, controller_ip: str) -> bool:
        """Выключение света через REST API"""
        try:
            # Попытка стандартного REST API выключения
            endpoints = [
                f"http://{controller_ip}/api/lighting/all/off",
                f"http://{controller_ip}/api/lighting/zone/all/off",
                f"http://{controller_ip}/api/building/lighting/off",
                f"http://{controller_ip}/api/system/lighting/off",
                f"http://{controller_ip}/rest/lighting/all/off"
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.post(endpoint, timeout=5)
                    if response.status_code in [200, 201, 202]:
                        print(f"✅ Свет выключен через REST API: {endpoint}")
                        return True
                except:
                    continue
            
            # Попытка с базовой аутентификацией
            auth_endpoints = [
                f"http://{controller_ip}/api/control/lighting",
                f"http://{controller_ip}/api/command"
            ]
            
            for endpoint in auth_endpoints:
                try:
                    data = {
                        "command": "lights_off",
                        "zone": "all",
                        "action": "off"
                    }
                    response = requests.post(
                        endpoint, 
                        json=data,
                        timeout=5,
                        auth=('admin', 'admin')  # Стандартные учетные данные
                    )
                    if response.status_code in [200, 201]:
                        print(f"✅ Свет выключен через REST с аутентификацией")
                        return True
                except:
                    continue
                    
        except Exception as e:
            print(f"❌ Ошибка REST API: {e}")
            
        return False

    def turn_off_lights_via_modbus(self, controller_ip: str) -> bool:
        """Выключение света через Modbus TCP"""
        try:
            # Создаем Modbus TCP запрос для выключения всех выходов
            # Function Code 5 - Write Single Coil (выключение реле)
            modbus_message = bytes.fromhex('00010000000601050000FF00')  # Broadcast выключение
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((controller_ip, 502))
            sock.send(modbus_message)
            response = sock.recv(1024)
            sock.close()
            
            print(f"✅ Команда Modbus отправлена на {controller_ip}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка Modbus: {e}")
            return False

    def turn_off_lights_via_knx(self, controller_ip: str) -> bool:
        """Выключение света через KNX/IP"""
        try:
            # KNX/IP пакет для выключения общего освещения
            knx_packet = bytes.fromhex(
                '0610020500140801c0a8016404d200000000000000000000'
            )
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            sock.sendto(knx_packet, (controller_ip, 3671))
            sock.close()
            
            print(f"✅ KNX команда отправлена на {controller_ip}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка KNX: {e}")
            return False

    def turn_off_lights_via_bacnet(self, controller_ip: str) -> bool:
        """Выключение света через BACnet"""
        try:
            # BACnet Who-Is запрос с командой выключения
            bacnet_packet = bytes.fromhex(
                '810b000c0120ffff00ff10080c023e0000003f'
            )
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            sock.sendto(bacnet_packet, (controller_ip, 47808))
            sock.close()
            
            print(f"✅ BACnet команда отправлена на {controller_ip}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка BACnet: {e}")
            return False

    def turn_off_lights_via_mqtt(self, controller_ip: str) -> bool:
        """Выключение света через MQTT"""
        try:
            # Простой MQTT CONNECT пакет с командой выключения
            mqtt_message = bytes.fromhex(
                '102600044d5154540402003c001a6275696c64696e672f6c69676874696e672f616c6c2f6f6666'
            )
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((controller_ip, 1883))
            sock.send(mqtt_message)
            sock.close()
            
            print(f"✅ MQTT команда отправлена на {controller_ip}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка MQTT: {e}")
            return False

    def emergency_light_off(self, controller_ip: str, protocol: str) -> bool:
        """Аварийное выключение освещения"""
        print(f"🚨 Попытка аварийного выключения через {protocol}...")
        
        if protocol == 'rest_api':
            return self.turn_off_lights_via_rest(controller_ip)
        elif protocol == 'modbus':
            return self.turn_off_lights_via_modbus(controller_ip)
        elif protocol == 'knx':
            return self.turn_off_lights_via_knx(controller_ip)
        elif protocol == 'bacnet':
            return self.turn_off_lights_via_bacnet(controller_ip)
        elif protocol == 'mqtt':
            return self.turn_off_lights_via_mqtt(controller_ip)
        else:
            # Пробуем все методы для неизвестного протокола
            methods = [
                self.turn_off_lights_via_rest,
                self.turn_off_lights_via_modbus,
                self.turn_off_lights_via_knx
            ]
            
            for method in methods:
                if method(controller_ip):
                    return True
                    
        return False

    def building_wide_light_off(self):
        """Основная функция выключения освещения во всем здании"""
        print("🏢 Запуск процедуры выключения освещения здания")
        print("=" * 50)
        
        # Обнаружение контроллеров
        controllers = self.discover_building_controllers()
        
        if not controllers:
            print("❌ Контроллеры управления зданием не найдены")
            print("💡 Попробуйте настроить IP-адреса в скрипте под вашу сеть")
            return False
        
        print(f"📊 Найдено контроллеров: {len(controllers)}")
        
        # Попытка выключения через каждый найденный контроллер
        success = False
        for controller in controllers:
            print(f"\n🔄 Обработка контроллера {controller['ip']} ({controller['protocol']})...")
            
            if self.emergency_light_off(controller['ip'], controller['protocol']):
                success = True
                print(f"🎉 УСПЕХ! Освещение выключено через {controller['protocol']}")
                break
            else:
                print(f"⚠️ Не удалось выключить через {controller['protocol']}")
        
        if success:
            print("\n" + "=" * 50)
            print("✅ ОСВЕЩЕНИЕ ВО ВСЕМ ЗДАНИИ ВЫКЛЮЧЕНО")
            print("=" * 50)
        else:
            print("\n❌ Не удалось выключить освещение ни через один контроллер")
            print("💡 Проверьте:")
            print("   - Настройки сети")
            print("   - IP-адреса контроллеров")
            print("   - Протоколы управления")
        
        return success

def main():
    """Основная функция"""
    print("🏢 Система управления освещением здания")
    print("⚠️  ВНИМАНИЕ: Только для авторизованного персонала!")
    print("⚠️  Использование без разрешения запрещено!")
    
    # Подтверждение действия
    confirm = input("\nВы уверены, что хотите выключить освещение во всем здании? (yes/NO): ")
    if confirm.lower() != 'yes':
        print("❌ Операция отменена")
        return
    
    # Дополнительное подтверждение
    safety_check = input("Это действие может нарушить работу здания. Продолжить? (CONFIRM/NO): ")
    if safety_check.upper() != 'CONFIRM':
        print("❌ Операция отменена по соображениям безопасности")
        return
    
    # Запуск процедуры
    controller = BuildingLightController()
    controller.building_wide_light_off()

if __name__ == "__main__":
    main()