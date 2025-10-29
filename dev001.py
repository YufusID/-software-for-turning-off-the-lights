import requests
import socket
import json
import time
import logging
from typing import Dict, List, Optional
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BMSLightController:
    def __init__(self, controller_ip: str, port: int = 80, username: str = None, password: str = None):
        """
        Инициализация контроллера BMS
        
        :param controller_ip: IP адрес BMS контроллера
        :param port: Порт (обычно 80, 443, 8080)
        :param username: Логин для аутентификации
        :param password: Пароль для аутентификации
        """
        self.controller_ip = controller_ip
        self.port = port
        self.base_url = f"http://{controller_ip}:{port}"
        self.https_base_url = f"https://{controller_ip}:{port}"
        self.auth = (username, password) if username and password else None
        self.session = requests.Session()
        
        if self.auth:
            self.session.auth = self.auth
        
        self.session.headers.update({
            'User-Agent': 'BMS-Light-Controller/1.0',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def discover_bms_protocol(self) -> Optional[str]:
        """
        Автоопределение протокола BMS контроллера
        """
        protocols = [
            self._try_bacnet,
            self._try_modbus,
            self._try_knx,
            self._try_lonworks,
            self._try_rest_api,
            self._try_soap_api,
            self._try_simple_http
        ]
        
        for protocol_test in protocols:
            try:
                protocol_name = protocol_test()
                if protocol_name:
                    logger.info(f"Обнаружен протокол: {protocol_name}")
                    return protocol_name
            except Exception as e:
                logger.debug(f"Протокол {protocol_test.__name__} не поддерживается: {e}")
                continue
        
        return None
    
    def _try_rest_api(self) -> Optional[str]:
        """Проверка REST API"""
        endpoints = [
            '/api/v1/lights',
            '/api/lights',
            '/rest/lighting',
            '/bms/api/control',
            '/lighting/zones',
            '/api/lighting'
        ]
        
        for endpoint in endpoints:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}", timeout=5, verify=False)
                if response.status_code == 200:
                    return "REST API"
            except:
                continue
        return None
    
    def _try_bacnet(self) -> Optional[str]:
        """Проверка BACnet"""
        try:
            # BACnet обычно использует порт 47808
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                result = s.connect_ex((self.controller_ip, 47808))
                if result == 0:
                    return "BACnet"
        except:
            pass
        return None
    
    def _try_modbus(self) -> Optional[str]:
        """Проверка Modbus"""
        modbus_ports = [502, 510, 1502]
        for port in modbus_ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    result = s.connect_ex((self.controller_ip, port))
                    if result == 0:
                        return "Modbus"
            except:
                continue
        return None
    
    def _try_knx(self) -> Optional[str]:
        """Проверка KNX"""
        knx_ports = [3671, 3672]
        for port in knx_ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    result = s.connect_ex((self.controller_ip, port))
                    if result == 0:
                        return "KNX"
            except:
                continue
        return None
    
    def _try_lonworks(self) -> Optional[str]:
        """Проверка LonWorks"""
        try:
            # LonWorks часто использует порт 1628
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                result = s.connect_ex((self.controller_ip, 1628))
                if result == 0:
                    return "LonWorks"
        except:
            pass
        return None
    
    def _try_soap_api(self) -> Optional[str]:
        """Проверка SOAP API"""
        try:
            headers = {'Content-Type': 'text/xml; charset=utf-8'}
            soap_body = '''<?xml version="1.0" encoding="utf-8"?>
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <GetSystemStatus xmlns="http://tempuri.org/"/>
                </soap:Body>
            </soap:Envelope>'''
            
            response = self.session.post(
                f"{self.base_url}/wsdl",
                data=soap_body,
                headers=headers,
                timeout=5,
                verify=False
            )
            if response.status_code == 200 and 'xml' in response.headers.get('Content-Type', ''):
                return "SOAP API"
        except:
            pass
        return None
    
    def _try_simple_http(self) -> Optional[str]:
        """Проверка простого HTTP интерфейса"""
        endpoints = [
            '/lightoff.cgi',
            '/control.cgi',
            '/cmd.xml',
            '/status.xml',
            '/api.cgi'
        ]
        
        for endpoint in endpoints:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}", timeout=5, verify=False)
                if response.status_code == 200:
                    return "Simple HTTP"
            except:
                continue
        return None
    
    def get_lighting_zones(self) -> List[Dict]:
        """
        Получение списка зон освещения
        """
        try:
            # Попробуем различные endpoints для получения зон
            endpoints = [
                '/api/lighting/zones',
                '/bms/lighting',
                '/zones',
                '/api/zones',
                '/lighting'
            ]
            
            for endpoint in endpoints:
                try:
                    response = self.session.get(
                        f"{self.base_url}{endpoint}",
                        timeout=10,
                        verify=False
                    )
                    if response.status_code == 200:
                        return response.json()
                except:
                    continue
            
            logger.warning("Не удалось получить список зон освещения")
            return []
            
        except Exception as e:
            logger.error(f"Ошибка при получении зон освещения: {e}")
            return []
    
    def turn_off_all_lights(self) -> bool:
        """
        Выключение всего освещения в здании
        """
        methods = [
            self._turn_off_via_rest,
            self._turn_off_via_soap,
            self._turn_off_via_simple_http,
            self._turn_off_via_bacnet_simulation,
            self._turn_off_zone_by_zone
        ]
        
        for method in methods:
            try:
                if method():
                    logger.info("Все освещение выключено")
                    return True
            except Exception as e:
                logger.debug(f"Метод {method.__name__} не сработал: {e}")
                continue
        
        logger.error("Не удалось выключить освещение")
        return False
    
    def _turn_off_via_rest(self) -> bool:
        """Выключение через REST API"""
        endpoints = [
            ('/api/lighting/all/off', 'POST'),
            ('/bms/lighting/off', 'POST'),
            ('/api/control/lighting/off', 'POST'),
            ('/lighting/off', 'POST'),
            ('/cmd/lightsoff', 'GET')
        ]
        
        for endpoint, method in endpoints:
            try:
                if method == 'POST':
                    response = self.session.post(
                        f"{self.base_url}{endpoint}",
                        json={"state": "off", "command": "all_off"},
                        timeout=10,
                        verify=False
                    )
                else:
                    response = self.session.get(
                        f"{self.base_url}{endpoint}",
                        timeout=10,
                        verify=False
                    )
                
                if response.status_code in [200, 201, 202]:
                    return True
                    
            except:
                continue
        
        return False
    
    def _turn_off_via_soap(self) -> bool:
        """Выключение через SOAP API"""
        try:
            soap_body = '''<?xml version="1.0" encoding="utf-8"?>
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <TurnOffAllLights xmlns="http://tempuri.org/"/>
                </soap:Body>
            </soap:Envelope>'''
            
            headers = {'Content-Type': 'text/xml; charset=utf-8'}
            response = self.session.post(
                f"{self.base_url}/WebService.asmx",
                data=soap_body,
                headers=headers,
                timeout=10,
                verify=False
            )
            
            return response.status_code == 200
            
        except:
            return False
    
    def _turn_off_via_simple_http(self) -> bool:
        """Выключение через простые HTTP команды"""
        commands = [
            '/lightoff.cgi?all=1',
            '/control.cgi?cmd=lightsoff',
            '/cmd.cgi?light=off',
            '/api.cgi?action=lightoff',
            '/switch.cgi?all=off'
        ]
        
        for command in commands:
            try:
                response = self.session.get(
                    f"{self.base_url}{command}",
                    timeout=10,
                    verify=False
                )
                if response.status_code == 200:
                    return True
            except:
                continue
        
        return False
    
    def _turn_off_via_bacnet_simulation(self) -> bool:
        """
        Эмуляция BACnet команды (для некоторых систем)
        """
        try:
            # Некоторые BMS принимают BACnet-like команды через HTTP
            bacnet_data = {
                "objectType": "binaryOutput",
                "objectInstance": "all",
                "property": "presentValue",
                "value": "inactive"
            }
            
            response = self.session.post(
                f"{self.base_url}/bacnet/command",
                json=bacnet_data,
                timeout=10,
                verify=False
            )
            
            return response.status_code == 200
            
        except:
            return False
    
    def _turn_off_zone_by_zone(self) -> bool:
        """
        Последовательное выключение по зонам
        """
        try:
            zones = self.get_lighting_zones()
            if not zones:
                logger.warning("Не найдены зоны для выключения")
                return False
            
            success_count = 0
            for zone in zones:
                zone_id = zone.get('id', zone.get('zoneId', zone.get('name')))
                if self.turn_off_zone(zone_id):
                    success_count += 1
                    logger.info(f"Зона {zone_id} выключена")
                    time.sleep(0.5)  # Задержка между командами
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Ошибка при выключении по зонам: {e}")
            return False
    
    def turn_off_zone(self, zone_id: str) -> bool:
        """
        Выключение конкретной зоны
        """
        endpoints = [
            f'/api/lighting/zones/{zone_id}/off',
            f'/bms/lighting/zone/{zone_id}/off',
            f'/api/control/zone/{zone_id}',
            f'/zone/{zone_id}/off'
        ]
        
        for endpoint in endpoints:
            try:
                response = self.session.post(
                    f"{self.base_url}{endpoint}",
                    json={"state": "off"},
                    timeout=5,
                    verify=False
                )
                if response.status_code in [200, 201, 202]:
                    return True
            except:
                continue
        
        return False
    
    def get_system_status(self) -> Dict:
        """
        Получение статуса системы
        """
        try:
            endpoints = ['/api/status', '/status', '/system/status', '/bms/status']
            
            for endpoint in endpoints:
                try:
                    response = self.session.get(
                        f"{self.base_url}{endpoint}",
                        timeout=5,
                        verify=False
                    )
                    if response.status_code == 200:
                        return response.json()
                except:
                    continue
            
            return {"status": "unknown", "error": "Cannot retrieve status"}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Пример использования
def main():
    # Конфигурация (замените на реальные параметры)
    CONFIG = {
        "controller_ip": "192.168.1.100",  # IP BMS контроллера
        "port": 80,
        "username": "admin",              # Логин
        "password": "password",           # Пароль
        "timeout": 30
    }
    
    # Создаем контроллер
    logger.info("Инициализация BMS контроллера...")
    bms_controller = BMSLightController(
        controller_ip=CONFIG["controller_ip"],
        port=CONFIG["port"],
        username=CONFIG["username"],
        password=CONFIG["password"]
    )
    
    # Проверяем подключение
    logger.info("Проверка подключения к BMS контроллеру...")
    status = bms_controller.get_system_status()
    logger.info(f"Статус системы: {status}")
    
    # Автоопределение протокола
    protocol = bms_controller.discover_bms_protocol()
    if protocol:
        logger.info(f"Работаем через протокол: {protocol}")
    else:
        logger.warning("Протокол не определен, пробуем стандартные методы")
    
    # Получаем зоны освещения
    logger.info("Получение списка зон освещения...")
    zones = bms_controller.get_lighting_zones()
    if zones:
        logger.info(f"Найдено зон освещения: {len(zones)}")
        for zone in zones[:5]:  # Показываем первые 5 зон
            logger.info(f"  - {zone.get('name', zone.get('id', 'Unknown'))}")
    
    # Выключаем все освещение
    logger.info("Выключение всего освещения...")
    success = bms_controller.turn_off_all_lights()
    
    if success:
        logger.info("✅ Освещение успешно выключено!")
        
        # Проверяем статус после выключения
        time.sleep(3)
        final_status = bms_controller.get_system_status()
        logger.info(f"Финальный статус: {final_status}")
    else:
        logger.error("❌ Не удалось выключить освещение")

if __name__ == "__main__":
    main()