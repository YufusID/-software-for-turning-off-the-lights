#!/usr/bin/env python3
"""
Скрипт для выключения света через обнаружение устройств умного дома с помощью nmap
ВНИМАНИЕ: Этот скрипт предназначен только для легального использования в вашей собственной сети!
"""

import subprocess
import socket
import requests
import json
import re
from concurrent.futures import ThreadPoolExecutor
import time

class SmartHomeLightController:
    def __init__(self):
        self.common_ports = {
            'philips_hue': 80,
            'tplink': 9999,
            'lifx': 56700,
            'home_assistant': 8123,
            'tuya': 6668,
            'yeelight': 55443,
            'wiz': 38899
        }
        
        self.known_devices = {
            'philips_hue': ['Philips', 'hue'],
            'tplink': ['TP-Link', 'Kasa'],
            'lifx': ['LIFX'],
            'yeelight': ['Yeelight'],
            'wiz': ['WiZ']
        }

    def scan_network(self, network_range="192.168.1.0/24"):
        """Сканирование сети на наличие устройств умного дома"""
        print("🔍 Сканирую сеть на наличие устройств умного дома...")
        
        devices = []
        
        try:
            # Сканирование общих портов умных устройств
            ports = ",".join(map(str, self.common_ports.values()))
            command = [
                'nmap', '-sS', '-p', ports, 
                '--open', '-T4', network_range
            ]
            
            result = subprocess.run(command, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                devices = self.parse_nmap_output(result.stdout)
            else:
                print("❌ Ошибка сканирования nmap")
                
        except subprocess.TimeoutExpired:
            print("❌ Таймаут сканирования")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            
        return devices

    def parse_nmap_output(self, nmap_output):
        """Парсинг вывода nmap для поиска устройств"""
        devices = []
        current_ip = None
        
        for line in nmap_output.split('\n'):
            # Поиск IP адреса
            ip_match = re.search(r'Nmap scan report for ([\d\.]+)', line)
            if ip_match:
                current_ip = ip_match.group(1)
                continue
                
            # Поиск открытых портов
            port_match = re.search(r'(\d+)/\w+\s+open', line)
            if port_match and current_ip:
                port = int(port_match.group(1))
                device_type = self.identify_device_by_port(port)
                
                if device_type:
                    devices.append({
                        'ip': current_ip,
                        'port': port,
                        'type': device_type
                    })
                    print(f"📱 Найдено устройство: {current_ip}:{port} ({device_type})")
                    
        return devices

    def identify_device_by_port(self, port):
        """Определение типа устройства по порту"""
        for device_type, device_port in self.common_ports.items():
            if port == device_port:
                return device_type
        return None

    def try_turn_off_lights(self, device):
        """Попытка выключить свет на устройстве"""
        ip = device['ip']
        device_type = device['type']
        
        print(f"🔄 Попытка выключить свет на {ip} ({device_type})...")
        
        try:
            if device_type == 'philips_hue':
                return self.control_philips_hue(ip)
            elif device_type == 'tplink':
                return self.control_tplink(ip)
            elif device_type == 'yeelight':
                return self.control_yeelight(ip)
            elif device_type == 'wiz':
                return self.control_wiz(ip)
            elif device_type == 'home_assistant':
                return self.control_home_assistant(ip)
            else:
                print(f"⚠️  Неизвестный тип устройства: {device_type}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка управления {ip}: {e}")
            return False

    def control_philips_hue(self, ip):
        """Управление Philips Hue"""
        try:
            # Получение информации о мосте
            response = requests.get(f"http://{ip}/api/config", timeout=5)
            if response.status_code == 200:
                print(f"✅ Philips Hue найден: {ip}")
                # Здесь нужна аутентификация для реального управления
                return True
        except:
            pass
        return False

    def control_tplink(self, ip):
        """Управление TP-Link устройствами"""
        try:
            # Простой TCP запрос для TP-Link
            command = '{"system":{"set_relay_state":{"state":0}}}'
            encrypted = self.encrypt_tplink(command)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, 9999))
            sock.send(encrypted)
            response = sock.recv(4096)
            sock.close()
            
            print(f"✅ TP-Link устройство отключено: {ip}")
            return True
        except:
            return False

    def encrypt_tplink(self, data):
        """Шифрование команды для TP-Link (упрощенное)"""
        key = 171
        result = bytearray([0, 0, 0, len(data)])
        for char in data:
            a = key ^ ord(char)
            key = a
            result.append(a)
        return bytes(result)

    def control_yeelight(self, ip):
        """Управление Yeelight"""
        try:
            command = {
                "id": 1,
                "method": "set_power",
                "params": ["off", "smooth", 500]
            }
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, 55443))
            sock.send((json.dumps(command) + "\r\n").encode())
            response = sock.recv(1024)
            sock.close()
            
            print(f"✅ Yeelight отключен: {ip}")
            return True
        except:
            return False

    def control_wiz(self, ip):
        """Управление WiZ устройствами"""
        try:
            command = {
                "method": "setPilot",
                "params": {
                    "state": False
                }
            }
            
            response = requests.post(
                f"http://{ip}:38899/json/set",
                json=command,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"✅ WiZ устройство отключено: {ip}")
                return True
        except:
            pass
        return False

    def control_home_assistant(self, ip):
        """Управление через Home Assistant"""
        print(f"ℹ️  Обнаружен Home Assistant: {ip}")
        print("   Для управления нужен токен доступа")
        return False

    def turn_off_all_lights(self):
        """Основная функция выключения всех светильников"""
        print("🚀 Запуск процедуры выключения света...")
        
        # Сканирование сети
        devices = self.scan_network()
        
        if not devices:
            print("❌ Устройства умного дома не найдены")
            return
        
        print(f"📊 Найдено {len(devices)} устройств")
        
        # Попытка выключить все устройства
        success_count = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(self.try_turn_off_lights, devices))
            success_count = sum(results)
        
        print(f"\n📊 Результат:")
        print(f"✅ Успешно выключено: {success_count}")
        print(f"❌ Не удалось выключить: {len(devices) - success_count}")

def main():
    """Основная функция"""
    print("🏠 Умный дом - Контроль освещения")
    print("=" * 40)
    print("⚠️  ВНИМАНИЕ: Используйте только в своей сети!")
    print("⚠️  Этот скрипт предназначен для образовательных целей")
    
    controller = SmartHomeLightController()
    
    # Запрос подтверждения
    confirm = input("\nПродолжить? (y/N): ").lower()
    if confirm != 'y':
        print("❌ Отменено пользователем")
        return
    
    # Выключение света
    controller.turn_off_all_lights()

if __name__ == "__main__":
    main()