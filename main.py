"""
Метеостанция - Приложение для работы с метеостанцией на nRF52820
Протокол: Версия 1 от 12.11.2023
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelHeader
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import StringProperty, ListProperty
from kivy.utils import platform
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.widget import Widget
import threading
import time
import struct
from datetime import datetime

# ==================== КОНСТАНТЫ ПРОТОКОЛА ====================

SERVICE_UUID = "01e10001-6d6f-43e6-9ea1-c1516874a6a8"
WRITE_CHAR_UUID = "01e10002-6d6f-43e6-9ea1-c1516874a6a8"
READ_CHAR_UUID = "01e10003-6d6f-43e6-9ea1-c1516874a6a8"

class CMD:
    GET_VALUE_P_T = 0x87
    GET_VALUE_H_T = 0x88
    GET_COEFF_P = 0x84
    GET_COEFF_T = 0x89
    GET_COEFF_H = 0x8A
    GET_COEFF_T1 = 0x8B
    GET_TIME_T = 0x15
    GET_DATETIME = 0x90
    GET_DEVICE_ID1 = 0x91
    GET_DEVICE_ID2 = 0x92
    GET_DEVICE_INFO = 0x93
    GET_DEVICE_VERSION = 0x94
    GET_DEVICE_STATUS = 0x95
    GET_LOG_SIZE = 0xA0
    GET_LOG_PARAMS = 0xA6
    
    SET_COEFF_P = 0x54
    SET_COEFF_T = 0x57
    SET_COEFF_H = 0x58
    SET_COEFF_T1 = 0x59
    SET_TIME_T = 0x55
    SET_DATETIME = 0x60
    SET_DEVICE_INFO = 0x63
    SET_LOG_PARAMS = 0xA7
    
    START_READ_LOG = 0xA1
    PAUSE_READ_LOG = 0xA2
    RESUME_READ_LOG = 0xA3
    STOP_READ_LOG = 0xA4
    RESET_LOG = 0xA5

class RSP:
    VALUE_P_T = 0x17
    VALUE_H_T = 0x18
    COEFF_P = 0x14
    COEFF_T = 0x19
    COEFF_H = 0x1A
    COEFF_T1 = 0x1B
    TIME_T = 0x15
    DATETIME = 0x20
    DEVICE_ID1 = 0x21
    DEVICE_ID2 = 0x22
    DEVICE_INFO = 0x23
    DEVICE_VERSION = 0x24
    DEVICE_STATUS = 0x25
    LOG_SIZE = 0xB0
    LOG_RECORD1 = 0xB1
    LOG_RECORD2 = 0xB2
    LOG_RECORD3 = 0xB3
    LOG_READ_COMPLETE = 0xB5
    LOG_PARAMS = 0xB6


# ==================== ПАРСЕР ПРОТОКОЛА ====================

class MeteorStationProtocol:
    @staticmethod
    def encode_float(value):
        return struct.pack('<f', float(value))
    
    @staticmethod
    def decode_float(data):
        return struct.unpack('<f', data)[0]
    
    @staticmethod
    def encode_uint32(value):
        return struct.pack('<I', int(value))
    
    @staticmethod
    def decode_uint32(data):
        return struct.unpack('<I', data)[0]
    
    @staticmethod
    def encode_uint16(value):
        return struct.pack('<H', int(value))
    
    @staticmethod
    def decode_uint16(data):
        return struct.unpack('<H', data)[0]
    
    @staticmethod
    def encode_request(cmd):
        return bytes([cmd, 0])
    
    @staticmethod
    def encode_set_coeff(cmd, a, b):
        data = bytes([cmd, 8])
        data += MeteorStationProtocol.encode_float(a)
        data += MeteorStationProtocol.encode_float(b)
        return data
    
    @staticmethod
    def encode_set_time_t(period_ms):
        data = bytes([CMD.SET_TIME_T, 4])
        data += MeteorStationProtocol.encode_uint32(period_ms)
        return data
    
    @staticmethod
    def encode_set_datetime(timestamp):
        data = bytes([CMD.SET_DATETIME, 4])
        data += MeteorStationProtocol.encode_uint32(timestamp)
        return data
    
    @staticmethod
    def parse_response(data):
        if len(data) < 2:
            return None
        
        cmd = data[0]
        length = data[1]
        
        if len(data) < 2 + length:
            return None
        
        payload = data[2:2 + length]
        result = {'cmd': cmd, 'length': length}
        
        try:
            if cmd == RSP.VALUE_P_T and length >= 8:
                result['type'] = 'pressure_temperature'
                result['pressure'] = MeteorStationProtocol.decode_float(payload[0:4])
                result['temperature'] = MeteorStationProtocol.decode_float(payload[4:8])
                
            elif cmd == RSP.VALUE_H_T and length >= 8:
                result['type'] = 'humidity_temperature'
                result['humidity'] = MeteorStationProtocol.decode_float(payload[0:4])
                result['temperature'] = MeteorStationProtocol.decode_float(payload[4:8])
                
            elif cmd in [RSP.COEFF_P, RSP.COEFF_T, RSP.COEFF_H, RSP.COEFF_T1] and length >= 8:
                channel = {RSP.COEFF_P: 'P', RSP.COEFF_T: 'T', 
                          RSP.COEFF_H: 'H', RSP.COEFF_T1: 'T1'}[cmd]
                result['type'] = f'coeff_{channel}'
                result['A'] = MeteorStationProtocol.decode_float(payload[0:4])
                result['B'] = MeteorStationProtocol.decode_float(payload[4:8])
                
            elif cmd == RSP.TIME_T and length >= 4:
                result['type'] = 'measurement_period'
                result['period_ms'] = MeteorStationProtocol.decode_uint32(payload[0:4])
                
            elif cmd == RSP.DATETIME and length >= 4:
                timestamp = MeteorStationProtocol.decode_uint32(payload[0:4])
                result['type'] = 'datetime'
                result['timestamp'] = timestamp
                result['datetime'] = datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M:%S')
                
            elif cmd == RSP.DEVICE_VERSION and length >= 4:
                version = MeteorStationProtocol.decode_uint32(payload[0:4])
                result['type'] = 'firmware_version'
                result['version'] = f"v{(version >> 24) & 0xFF}.{(version >> 16) & 0xFF}.{(version >> 8) & 0xFF}.{version & 0xFF}"
                
            elif cmd == RSP.DEVICE_INFO and length >= 8:
                creation = MeteorStationProtocol.decode_uint32(payload[0:4])
                sn = MeteorStationProtocol.decode_uint32(payload[4:8])
                result['type'] = 'device_info'
                result['creation_date'] = datetime.fromtimestamp(creation).strftime('%d.%m.%Y')
                result['serial_number'] = sn
                
            elif cmd == RSP.LOG_SIZE and length >= 4:
                result['type'] = 'log_size'
                result['log_size'] = MeteorStationProtocol.decode_uint32(payload[0:4])
                
            elif cmd == RSP.LOG_RECORD1 and length >= 10:
                result['type'] = 'log_record1'
                result['record_number'] = MeteorStationProtocol.decode_uint16(payload[0:2])
                result['timestamp'] = MeteorStationProtocol.decode_uint32(payload[2:6])
                result['datetime'] = datetime.fromtimestamp(result['timestamp']).strftime('%d.%m.%Y %H:%M:%S')
                result['pressure'] = MeteorStationProtocol.decode_float(payload[6:10])
                
            elif cmd == RSP.LOG_RECORD2 and length >= 10:
                result['type'] = 'log_record2'
                result['record_number'] = MeteorStationProtocol.decode_uint16(payload[0:2])
                result['temperature'] = MeteorStationProtocol.decode_float(payload[2:6])
                result['humidity'] = MeteorStationProtocol.decode_float(payload[6:10])
                
            elif cmd == RSP.LOG_RECORD3 and length >= 6:
                result['type'] = 'log_record3'
                result['record_number'] = MeteorStationProtocol.decode_uint16(payload[0:2])
                result['temperature_ext'] = MeteorStationProtocol.decode_float(payload[2:6])
                
            elif cmd == RSP.LOG_READ_COMPLETE:
                result['type'] = 'log_complete'
                
        except Exception as e:
            print(f"Parse error: {e}")
            result['error'] = str(e)
        
        return result


# ==================== BLE МЕНЕДЖЕР ====================

class MeteorStationBLE:
    def __init__(self):
        self.device = None
        self.connected = False
        self.write_char = None
        self.read_char = None
        self.data_callback = None
        self.connection_callback = None
        
        if platform == 'android':
            self._init_android_ble()
    
    def _init_android_ble(self):
        try:
            from jnius import autoclass, cast, PythonJavaClass, java_method
            
            self.BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
            self.BluetoothManager = autoclass('android.bluetooth.BluetoothManager')
            self.BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
            self.BluetoothGatt = autoclass('android.bluetooth.BluetoothGatt')
            self.BluetoothGattCharacteristic = autoclass('android.bluetooth.BluetoothGattCharacteristic')
            self.BluetoothGattDescriptor = autoclass('android.bluetooth.BluetoothGattDescriptor')
            self.BluetoothProfile = autoclass('android.bluetooth.BluetoothProfile')
            self.BluetoothGattService = autoclass('android.bluetooth.BluetoothGattService')
            
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            self.bluetooth_manager = activity.getSystemService(
                autoclass('android.content.Context').BLUETOOTH_SERVICE
            )
            self.bluetooth_manager = cast('android.bluetooth.BluetoothManager', 
                                         self.bluetooth_manager)
            self.bluetooth_adapter = self.bluetooth_manager.getAdapter()
            
        except Exception as e:
            print(f"BLE init error: {e}")
    
    def scan(self, duration=5, callback=None):
        self.scan_callback = callback
        
        if platform == 'android':
            try:
                from jnius import PythonJavaClass, java_method
                
                class ScanCallback(PythonJavaClass):
                    __javainterfaces__ = ['android/bluetooth/le/ScanCallback']
                    
                    def __init__(self, ble):
                        super().__init__()
                        self.ble = ble
                        self.devices = {}
                    
                    @java_method('(ILandroid/bluetooth/le/ScanResult;)V')
                    def onScanResult(self, callbackType, result):
                        device = result.getDevice()
                        name = device.getName()
                        address = device.getAddress()
                        
                        scan_record = result.getScanRecord()
                        if scan_record:
                            uuids = scan_record.getServiceUuids()
                            if uuids:
                                for uuid in uuids.toArray():
                                    if str(uuid).upper() == SERVICE_UUID.upper():
                                        device_info = {
                                            'name': name if name else 'Метеостанция',
                                            'address': address,
                                            'rssi': result.getRssi(),
                                            'device': device
                                        }
                                        self.devices[address] = device_info
                                        
                                        if self.ble.scan_callback:
                                            Clock.schedule_once(
                                                lambda dt, d=list(self.devices.values()): 
                                                self.ble.scan_callback(d), 0
                                            )
                                        break
                
                scanner = self.bluetooth_adapter.getBluetoothLeScanner()
                self.scan_callback_obj = ScanCallback(self)
                scanner.startScan(self.scan_callback_obj)
                
                def stop_scan(dt):
                    try:
                        scanner.stopScan(self.scan_callback_obj)
                    except:
                        pass
                
                Clock.schedule_once(stop_scan, duration)
                
            except Exception as e:
                print(f"Scan error: {e}")
    
    def connect(self, device_info, callback=None):
        self.connection_callback = callback
        
        try:
            device = device_info['device']
            
            if platform == 'android':
                from jnius import PythonJavaClass, java_method
                
                class GattCallback(PythonJavaClass):
                    __javainterfaces__ = ['android/bluetooth/BluetoothGattCallback']
                    
                    def __init__(self, ble):
                        super().__init__()
                        self.ble = ble
                    
                    @java_method('(Landroid/bluetooth/BluetoothGatt;II)V')
                    def onConnectionStateChange(self, gatt, status, newState):
                        if newState == self.ble.BluetoothProfile.STATE_CONNECTED:
                            self.ble.connected = True
                            self.ble.device = gatt
                            gatt.discoverServices()
                        elif newState == self.ble.BluetoothProfile.STATE_DISCONNECTED:
                            self.ble.connected = False
                            self.ble.device = None
                            self.ble.write_char = None
                            self.ble.read_char = None
                            if self.ble.connection_callback:
                                Clock.schedule_once(
                                    lambda dt: self.ble.connection_callback(False), 0
                                )
                    
                    @java_method('(Landroid/bluetooth/BluetoothGatt;I)V')
                    def onServicesDiscovered(self, gatt, status):
                        if status == self.ble.BluetoothGatt.GATT_SUCCESS:
                            service = gatt.getService(
                                autoclass('java.util.UUID').fromString(SERVICE_UUID)
                            )
                            if service:
                                self.ble.write_char = service.getCharacteristic(
                                    autoclass('java.util.UUID').fromString(WRITE_CHAR_UUID)
                                )
                                self.ble.read_char = service.getCharacteristic(
                                    autoclass('java.util.UUID').fromString(READ_CHAR_UUID)
                                )
                                
                                if self.ble.read_char:
                                    gatt.setCharacteristicNotification(self.ble.read_char, True)
                                    
                                    descriptor = self.ble.read_char.getDescriptor(
                                        autoclass('java.util.UUID')
                                        .fromString("00002902-0000-1000-8000-00805F9B34FB")
                                    )
                                    if descriptor:
                                        descriptor.setValue(
                                            self.ble.BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                                        )
                                        gatt.writeDescriptor(descriptor)
                            
                            if self.ble.connection_callback:
                                Clock.schedule_once(
                                    lambda dt: self.ble.connection_callback(True), 0
                                )
                    
                    @java_method('(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;[B)V')
                    def onCharacteristicChanged(self, gatt, characteristic, value):
                        if self.ble.data_callback:
                            data = bytes(value)
                            parsed = MeteorStationProtocol.parse_response(data)
                            if parsed:
                                Clock.schedule_once(
                                    lambda dt, p=parsed: self.ble.data_callback(p), 0
                                )
                
                self.gatt_callback = GattCallback(self)
                device.connectGatt(
                    autoclass('org.kivy.android.PythonActivity').mActivity,
                    False,
                    self.gatt_callback,
                    self.BluetoothDevice.TRANSPORT_LE
                )
                return True
                
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def send_command(self, data):
        if not self.connected or not self.device or not self.write_char:
            return False
        
        try:
            if isinstance(data, bytes):
                payload = data
            else:
                payload = bytes(data)
            
            self.write_char.setValue(payload)
            self.device.writeCharacteristic(self.write_char)
            return True
        except Exception as e:
            print(f"Send error: {e}")
            return False
    
    def disconnect(self):
        if self.device:
            try:
                self.device.disconnect()
                self.device.close()
            except:
                pass
            self.device = None
            self.connected = False
            self.write_char = None
            self.read_char = None
            return True
        return False


# ==================== ГЛАВНОЕ ПРИЛОЖЕНИЕ ====================

class MeteorStationApp(App):
    connection_status = StringProperty("Отключено")
    device_name = StringProperty("Метеостанция")
    device_address = StringProperty("")
    
    pressure = StringProperty("---")
    temperature = StringProperty("---")
    humidity = StringProperty("---")
    temperature_ext = StringProperty("---")
    
    measurement_period = StringProperty("---")
    device_time = StringProperty("---")
    firmware_version = StringProperty("---")
    serial_number = StringProperty("---")
    
    coeff_p_a = StringProperty("1.0")
    coeff_p_b = StringProperty("0.0")
    coeff_t_a = StringProperty("1.0")
    coeff_t_b = StringProperty("0.0")
    coeff_h_a = StringProperty("1.0")
    coeff_h_b = StringProperty("0.0")
    coeff_t1_a = StringProperty("1.0")
    coeff_t1_b = StringProperty("0.0")
    
    log_records = ListProperty([])
    log_size = StringProperty("0")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ble = MeteorStationBLE()
        self.ble.data_callback = self.on_data_received
        self.auto_update = False
        self.log_reading = False
        
        # Запрос разрешений для Android
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.BLUETOOTH,
                    Permission.BLUETOOTH_ADMIN,
                    Permission.BLUETOOTH_SCAN,
                    Permission.BLUETOOTH_CONNECT,
                    Permission.ACCESS_FINE_LOCATION,
                    Permission.ACCESS_COARSE_LOCATION
                ])
            except:
                pass
    
    def build(self):
        Window.clearcolor = (0.95, 0.95, 0.95, 1)
        
        main_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(15))
        main_layout.add_widget(self.create_connection_panel())
        
        tabs = TabbedPanel(do_default_tab=False, tab_width=dp(120))
        
        data_tab = TabbedPanelHeader(text='Текущие данные')
        data_tab.content = self.create_data_tab()
        tabs.add_widget(data_tab)
        
        coeff_tab = TabbedPanelHeader(text='Калибровка')
        coeff_tab.content = self.create_coeff_tab()
        tabs.add_widget(coeff_tab)
        
        settings_tab = TabbedPanelHeader(text='Настройки')
        settings_tab.content = self.create_settings_tab()
        tabs.add_widget(settings_tab)
        
        log_tab = TabbedPanelHeader(text='Журнал')
        log_tab.content = self.create_log_tab()
        tabs.add_widget(log_tab)
        
        info_tab = TabbedPanelHeader(text='Информация')
        info_tab.content = self.create_info_tab()
        tabs.add_widget(info_tab)
        
        main_layout.add_widget(tabs)
        return main_layout
    
    def create_connection_panel(self):
        panel = BoxLayout(size_hint=(1, 0.1), spacing=dp(10))
        
        with panel.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(0.9, 0.9, 0.9, 1)
            panel.rect = Rectangle(pos=panel.pos, size=panel.size)
            panel.bind(pos=self._update_rect, size=self._update_rect)
        
        status_layout = BoxLayout(orientation='vertical', size_hint=(0.5, 1))
        status_layout.add_widget(Label(
            text=f'Статус: {self.connection_status}',
            font_size='14sp',
            halign='left',
            color=(0.2, 0.6, 0.9, 1) if 'Подключено' in self.connection_status else (1, 0.3, 0.3, 1)
        ))
        status_layout.add_widget(Label(
            text=f'Устройство: {self.device_name}',
            font_size='12sp',
            halign='left',
            color=(0, 0, 0, 1)  # Чёрный цвет
        ))
        
        btn_layout = BoxLayout(size_hint=(0.5, 1), spacing=dp(5))
        
        self.scan_btn = Button(
            text='Сканировать',
            font_size='12sp',
            background_color=(0.2, 0.6, 0.9, 1),
            on_press=self.scan_devices
        )
        
        self.connect_btn = Button(
            text='Подключиться',
            font_size='12sp',
            background_color=(0.3, 0.8, 0.3, 1),
            disabled=True,
            on_press=self.toggle_connection
        )
        
        btn_layout.add_widget(self.scan_btn)
        btn_layout.add_widget(self.connect_btn)
        
        panel.add_widget(status_layout)
        panel.add_widget(btn_layout)
        
        return panel
    
    def _update_rect(self, instance, value):
        instance.rect.pos = instance.pos
        instance.rect.size = instance.size
    
    def create_data_tab(self):
        layout = GridLayout(cols=2, spacing=dp(20), padding=dp(20), size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))
        
        layout.add_widget(Label(text='Давление:', font_size='16sp', size_hint_y=None, height=dp(45)))
        layout.add_widget(Label(text=self.pressure, font_size='24sp', size_hint_y=None, height=dp(45)))
        
        layout.add_widget(Label(text='Температура:', font_size='16sp', size_hint_y=None, height=dp(45)))
        layout.add_widget(Label(text=self.temperature, font_size='24sp', size_hint_y=None, height=dp(45)))
        
        layout.add_widget(Label(text='Влажность:', font_size='16sp', size_hint_y=None, height=dp(45)))
        layout.add_widget(Label(text=self.humidity, font_size='24sp', size_hint_y=None, height=dp(45)))
        
        layout.add_widget(Label(text='Внешняя T:', font_size='16sp', size_hint_y=None, height=dp(45)))
        layout.add_widget(Label(text=self.temperature_ext, font_size='24sp', size_hint_y=None, height=dp(45)))
        
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(15))
        
        # Увеличенная ширина для "Давление/Темп"
        btn_layout.add_widget(Button(
            text='Давление/Темп',
            font_size='12sp',
            size_hint_x=0.6,
            on_press=lambda x: self.send_command(CMD.GET_VALUE_P_T)
        ))
        btn_layout.add_widget(Button(
            text='Влажность',
            font_size='12sp',
            size_hint_x=0.4,
            on_press=lambda x: self.send_command(CMD.GET_VALUE_H_T)
        ))
        
        layout.add_widget(Label(text=''))
        layout.add_widget(btn_layout)
        
        return layout
    
    def create_coeff_tab(self):
        # Максимально уплотнённый layout с подписями в тех же строках
        layout = GridLayout(cols=2, spacing=dp(8), padding=dp(10), size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))
        
        # === Канал P ===
        # Заголовок с подписью "Канал" в той же строке
        layout.add_widget(Label(
            text='Канал P:', 
            font_size='14sp', 
            bold=True, 
            size_hint_y=None, 
            height=dp(30),
            halign='left'
        ))
        layout.add_widget(Label(text=''))
        
        # A (подпись A слева, значение справа)
        layout.add_widget(Label(text='A:', size_hint_y=None, height=dp(28), font_size='12sp'))
        self.coeff_p_a_input = TextInput(
            text=self.coeff_p_a, 
            multiline=False, 
            size_hint_y=None, 
            height=dp(28),
            font_size='12sp'
        )
        layout.add_widget(self.coeff_p_a_input)
        
        # B (подпись B слева, значение справа)
        layout.add_widget(Label(text='B:', size_hint_y=None, height=dp(28), font_size='12sp'))
        self.coeff_p_b_input = TextInput(
            text=self.coeff_p_b, 
            multiline=False, 
            size_hint_y=None, 
            height=dp(28),
            font_size='12sp'
        )
        layout.add_widget(self.coeff_p_b_input)
        
        # Кнопки с подписью "Действия" в той же строке
        layout.add_widget(Label(
            text='Действия:', 
            size_hint_y=None, 
            height=dp(32), 
            font_size='12sp',
            halign='right'
        ))
        btn_p_layout = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(5))
        btn_p_layout.add_widget(Button(
            text='Чит',
            font_size='11sp',
            on_press=lambda x: self.send_command(CMD.GET_COEFF_P)
        ))
        btn_p_layout.add_widget(Button(
            text='Зап',
            font_size='11sp',
            on_press=self.set_coeff_p
        ))
        layout.add_widget(btn_p_layout)
        
        # Минимальный разделитель
        layout.add_widget(Widget(size_hint_y=None, height=dp(5)))
        layout.add_widget(Widget(size_hint_y=None, height=dp(5)))
        
        # === Канал T ===
        layout.add_widget(Label(
            text='Канал T:', 
            font_size='14sp', 
            bold=True, 
            size_hint_y=None, 
            height=dp(30),
            halign='left'
        ))
        layout.add_widget(Label(text=''))
        
        layout.add_widget(Label(text='A:', size_hint_y=None, height=dp(28), font_size='12sp'))
        self.coeff_t_a_input = TextInput(
            text=self.coeff_t_a, 
            multiline=False, 
            size_hint_y=None, 
            height=dp(28),
            font_size='12sp'
        )
        layout.add_widget(self.coeff_t_a_input)
        
        layout.add_widget(Label(text='B:', size_hint_y=None, height=dp(28), font_size='12sp'))
        self.coeff_t_b_input = TextInput(
            text=self.coeff_t_b, 
            multiline=False, 
            size_hint_y=None, 
            height=dp(28),
            font_size='12sp'
        )
        layout.add_widget(self.coeff_t_b_input)
        
        layout.add_widget(Label(text='Действия:', size_hint_y=None, height=dp(32), font_size='12sp', halign='right'))
        btn_t_layout = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(5))
        btn_t_layout.add_widget(Button(
            text='Чит',
            font_size='11sp',
            on_press=lambda x: self.send_command(CMD.GET_COEFF_T)
        ))
        btn_t_layout.add_widget(Button(
            text='Зап',
            font_size='11sp',
            on_press=self.set_coeff_t
        ))
        layout.add_widget(btn_t_layout)
        
        layout.add_widget(Widget(size_hint_y=None, height=dp(5)))
        layout.add_widget(Widget(size_hint_y=None, height=dp(5)))
        
        # === Канал H ===
        layout.add_widget(Label(
            text='Канал H:', 
            font_size='14sp', 
            bold=True, 
            size_hint_y=None, 
            height=dp(30),
            halign='left'
        ))
        layout.add_widget(Label(text=''))
        
        layout.add_widget(Label(text='A:', size_hint_y=None, height=dp(28), font_size='12sp'))
        self.coeff_h_a_input = TextInput(
            text=self.coeff_h_a, 
            multiline=False, 
            size_hint_y=None, 
            height=dp(28),
            font_size='12sp'
        )
        layout.add_widget(self.coeff_h_a_input)
        
        layout.add_widget(Label(text='B:', size_hint_y=None, height=dp(28), font_size='12sp'))
        self.coeff_h_b_input = TextInput(
            text=self.coeff_h_b, 
            multiline=False, 
            size_hint_y=None, 
            height=dp(28),
            font_size='12sp'
        )
        layout.add_widget(self.coeff_h_b_input)
        
        layout.add_widget(Label(text='Действия:', size_hint_y=None, height=dp(32), font_size='12sp', halign='right'))
        btn_h_layout = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(5))
        btn_h_layout.add_widget(Button(
            text='Чит',
            font_size='11sp',
            on_press=lambda x: self.send_command(CMD.GET_COEFF_H)
        ))
        btn_h_layout.add_widget(Button(
            text='Зап',
            font_size='11sp',
            on_press=self.set_coeff_h
        ))
        layout.add_widget(btn_h_layout)
        
        return layout
    
    def create_settings_tab(self):
        layout = GridLayout(cols=2, spacing=dp(20), padding=dp(20), size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))
        
        # Период измерений
        layout.add_widget(Label(text='Период:', font_size='16sp', bold=True, size_hint_y=None, height=dp(45)))
        layout.add_widget(Label(text=''))
        
        layout.add_widget(Label(text='Текущий:', size_hint_y=None, height=dp(40)))
        layout.add_widget(Label(text=self.measurement_period, size_hint_y=None, height=dp(40)))
        
        layout.add_widget(Label(text='Установить (мс):', size_hint_y=None, height=dp(40)))
        self.period_input = TextInput(text='1000', multiline=False, size_hint_y=None, height=dp(40))
        layout.add_widget(self.period_input)
        
        btn_period_layout = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(15))
        btn_period_layout.add_widget(Button(
            text='Прочитать',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.GET_TIME_T)
        ))
        btn_period_layout.add_widget(Button(
            text='Установить',
            font_size='12sp',
            on_press=self.set_measurement_period
        ))
        layout.add_widget(Label(text=''))
        layout.add_widget(btn_period_layout)
        
        layout.add_widget(Widget(size_hint_y=None, height=dp(20)))
        layout.add_widget(Widget(size_hint_y=None, height=dp(20)))
        
        # Дата и время
        layout.add_widget(Label(text='Дата/время:', font_size='16sp', bold=True, size_hint_y=None, height=dp(45)))
        layout.add_widget(Label(text=''))
        
        layout.add_widget(Label(text='На устройстве:', size_hint_y=None, height=dp(40)))
        layout.add_widget(Label(text=self.device_time, size_hint_y=None, height=dp(40)))
        
        btn_sync_layout = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(15))
        btn_sync_layout.add_widget(Button(
            text='Прочитать',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.GET_DATETIME)
        ))
        # Уменьшен шрифт для "Синхр."
        btn_sync_layout.add_widget(Button(
            text='Синхр.',
            font_size='11sp',
            size_hint_x=0.5,
            on_press=self.sync_datetime
        ))
        layout.add_widget(Label(text=''))
        layout.add_widget(btn_sync_layout)
        
        return layout
    
    def create_log_tab(self):
        layout = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(10))
        
        control_panel = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        control_panel.add_widget(Button(
            text='Размер',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.GET_LOG_SIZE)
        ))
        control_panel.add_widget(Button(
            text='Читать',
            font_size='12sp',
            on_press=self.start_read_log
        ))
        control_panel.add_widget(Button(
            text='Стоп',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.STOP_READ_LOG)
        ))
        layout.add_widget(control_panel)
        
        info_panel = BoxLayout(size_hint_y=None, height=dp(40))
        info_panel.add_widget(Label(text=f'Записей: {self.log_size}', font_size='14sp'))
        layout.add_widget(info_panel)
        
        self.log_list = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.log_list.bind(minimum_height=self.log_list.setter('height'))
        
        scroll = ScrollView()
        scroll.add_widget(self.log_list)
        layout.add_widget(scroll)
        
        return layout
    
    def create_info_tab(self):
        layout = GridLayout(cols=2, spacing=dp(20), padding=dp(20), size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))
        
        layout.add_widget(Label(text='Версия:', font_size='16sp', size_hint_y=None, height=dp(50)))
        layout.add_widget(Label(text=self.firmware_version, font_size='16sp', size_hint_y=None, height=dp(50)))
        
        layout.add_widget(Label(text='Серийный №:', font_size='16sp', size_hint_y=None, height=dp(50)))
        layout.add_widget(Label(text=self.serial_number, font_size='16sp', size_hint_y=None, height=dp(50)))
        
        layout.add_widget(Label(text='Дата произв.:', font_size='16sp', size_hint_y=None, height=dp(50)))
        layout.add_widget(Label(text='---', font_size='16sp', size_hint_y=None, height=dp(50)))
        
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(15))
        btn_layout.add_widget(Button(
            text='Инфо',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.GET_DEVICE_INFO)
        ))
        btn_layout.add_widget(Button(
            text='Версия',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.GET_DEVICE_VERSION)
        ))
        
        layout.add_widget(Label(text=''))
        layout.add_widget(btn_layout)
        
        return layout
    
    def scan_devices(self, instance):
        self.scan_btn.text = 'Сканирование...'
        self.scan_btn.disabled = True
        self.ble.scan(duration=5, callback=self.on_devices_found)
    
    def on_devices_found(self, devices):
        self.scan_btn.text = 'Сканировать'
        self.scan_btn.disabled = False
        
        if not devices:
            self.show_popup('Устройства не найдены', 
                          'Метеостанция не обнаружена.\n'
                          'Проверьте:\n'
                          '• Bluetooth включен\n'
                          '• Устройство включено\n'
                          '• Рядом с телефоном')
            return
        
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        
        for device in devices:
            btn = Button(
                text=f"{device['name']}\n{device['address']} (RSSI: {device['rssi']}dBm)",
                size_hint_y=None,
                height=dp(60),
                background_color=(0.2, 0.6, 0.9, 0.8)
            )
            btn.bind(on_press=lambda x, d=device: self.select_device(d))
            content.add_widget(btn)
        
        scroll = ScrollView(size_hint=(1, 0.8))
        scroll.add_widget(content)
        
        popup = Popup(
            title='Выберите метеостанцию',
            content=scroll,
            size_hint=(0.9, 0.8)
        )
        popup.open()
        self.device_popup = popup
    
    def select_device(self, device):
        self.selected_device = device
        self.device_name = device['name']
        self.device_address = device['address']
        self.connect_btn.disabled = False
        
        if hasattr(self, 'device_popup'):
            self.device_popup.dismiss()
    
    def toggle_connection(self, instance):
        if not self.ble.connected:
            self.connect_btn.text = 'Подключение...'
            self.connect_btn.disabled = True
            
            def connected(success):
                if success:
                    self.connection_status = "Подключено"
                    self.connect_btn.text = 'Отключиться'
                    self.connect_btn.disabled = False
                    self.scan_btn.disabled = True
                    
                    # Автоматически запрашиваем данные
                    self.send_command(CMD.GET_DEVICE_VERSION)
                    self.send_command(CMD.GET_DEVICE_INFO)
                    self.send_command(CMD.GET_TIME_T)
                    self.send_command(CMD.GET_VALUE_P_T)
                    self.send_command(CMD.GET_VALUE_H_T)
                else:
                    self.connection_status = "Ошибка подключения"
                    self.connect_btn.text = 'Подключиться'
                    self.connect_btn.disabled = False
                    self.show_popup('Ошибка', 'Не удалось подключиться к устройству')
            
            self.ble.connect(self.selected_device, callback=connected)
        else:
            self.ble.disconnect()
            self.connection_status = "Отключено"
            self.connect_btn.text = 'Подключиться'
            self.scan_btn.disabled = False
    
    def send_command(self, cmd):
        if self.ble.connected:
            data = MeteorStationProtocol.encode_request(cmd)
            return self.ble.send_command(data)
        return False
    
    def set_coeff_p(self, instance):
        try:
            a = float(self.coeff_p_a_input.text)
            b = float(self.coeff_p_b_input.text)
            data = MeteorStationProtocol.encode_set_coeff(CMD.SET_COEFF_P, a, b)
            self.ble.send_command(data)
            self.show_message('Коэффициенты P отправлены')
        except ValueError:
            self.show_popup('Ошибка', 'Введите корректные числа')
    
    def set_coeff_t(self, instance):
        try:
            a = float(self.coeff_t_a_input.text)
            b = float(self.coeff_t_b_input.text)
            data = MeteorStationProtocol.encode_set_coeff(CMD.SET_COEFF_T, a, b)
            self.ble.send_command(data)
            self.show_message('Коэффициенты T отправлены')
        except ValueError:
            self.show_popup('Ошибка', 'Введите корректные числа')
    
    def set_coeff_h(self, instance):
        try:
            a = float(self.coeff_h_a_input.text)
            b = float(self.coeff_h_b_input.text)
            data = MeteorStationProtocol.encode_set_coeff(CMD.SET_COEFF_H, a, b)
            self.ble.send_command(data)
            self.show_message('Коэффициенты H отправлены')
        except ValueError:
            self.show_popup('Ошибка', 'Введите корректные числа')
    
    def set_measurement_period(self, instance):
        try:
            period = int(self.period_input.text)
            data = MeteorStationProtocol.encode_set_time_t(period)
            self.ble.send_command(data)
            self.show_message(f'Период установлен: {period} мс')
        except ValueError:
            self.show_popup('Ошибка', 'Введите целое число')
    
    def sync_datetime(self, instance):
        timestamp = int(time.time())
        data = MeteorStationProtocol.encode_set_datetime(timestamp)
        self.ble.send_command(data)
        self.show_message('Время синхронизировано')
    
    def start_read_log(self, instance):
        self.log_records = []
        self.log_list.clear_widgets()
        self.send_command(CMD.START_READ_LOG)
        self.log_reading = True
        self.show_message('Чтение журнала...')
    
    def on_data_received(self, data):
        if 'type' not in data:
            return
        
        if data['type'] == 'pressure_temperature':
            self.pressure = f"{data['pressure']:.2f}"
            self.temperature = f"{data['temperature']:.1f}"
            
        elif data['type'] == 'humidity_temperature':
            self.humidity = f"{data['humidity']:.1f}"
            self.temperature_ext = f"{data['temperature']:.1f}"
            
        elif data['type'] == 'coeff_P':
            self.coeff_p_a = f"{data['A']:.6f}"
            self.coeff_p_b = f"{data['B']:.6f}"
            
        elif data['type'] == 'coeff_T':
            self.coeff_t_a = f"{data['A']:.6f}"
            self.coeff_t_b = f"{data['B']:.6f}"
            
        elif data['type'] == 'coeff_H':
            self.coeff_h_a = f"{data['A']:.6f}"
            self.coeff_h_b = f"{data['B']:.6f}"
            
        elif data['type'] == 'measurement_period':
            self.measurement_period = f"{data['period_ms']} мс"
            
        elif data['type'] == 'datetime':
            self.device_time = data['datetime']
            
        elif data['type'] == 'firmware_version':
            self.firmware_version = data['version']
            
        elif data['type'] == 'device_info':
            self.serial_number = str(data['serial_number'])
            
        elif data['type'] == 'log_size':
            self.log_size = str(data['log_size'])
            
        elif data['type'] in ['log_record1', 'log_record2', 'log_record3']:
            self.add_log_record(data)
            
        elif data['type'] == 'log_complete':
            self.show_message('Чтение журнала завершено')
            self.log_reading = False
    
    def add_log_record(self, data):
        record_layout = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40),
            spacing=dp(10),
            padding=dp(5)
        )
        
        if 'datetime' in data:
            record_layout.add_widget(Label(
                text=data['datetime'],
                size_hint=(0.3, 1),
                halign='left',
                font_size='12sp'
            ))
        
        if 'pressure' in data:
            record_layout.add_widget(Label(
                text=f"P: {data['pressure']:.2f}",
                size_hint=(0.2, 1),
                font_size='12sp'
            ))
        
        if 'temperature' in data:
            record_layout.add_widget(Label(
                text=f"T: {data['temperature']:.1f}",
                size_hint=(0.2, 1),
                font_size='12sp'
            ))
        
        if 'humidity' in data:
            record_layout.add_widget(Label(
                text=f"H: {data['humidity']:.1f}",
                size_hint=(0.2, 1),
                font_size='12sp'
            ))
        
        self.log_list.add_widget(record_layout)
    
    def show_popup(self, title, message):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(Label(text=message))
        
        btn = Button(text='OK', size_hint_y=None, height=dp(40))
        content.add_widget(btn)
        
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.4))
        btn.bind(on_press=popup.dismiss)
        popup.open()
    
    def show_message(self, message):
        print(f"Message: {message}")


if __name__ == '__main__':
    MeteorStationApp().run()
