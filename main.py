"""
Метеостанция - Приложение для работы с метеостанцией на nRF52820
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
from kivy.properties import StringProperty
from kivy.metrics import dp
from kivy.core.window import Window
import time

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
    GET_TIME_T = 0x15
    GET_DATETIME = 0x90
    GET_DEVICE_INFO = 0x93
    GET_DEVICE_VERSION = 0x94
    GET_LOG_SIZE = 0xA0
    
    SET_COEFF_P = 0x54
    SET_COEFF_T = 0x57
    SET_COEFF_H = 0x58
    SET_TIME_T = 0x55
    SET_DATETIME = 0x60
    
    START_READ_LOG = 0xA1
    STOP_READ_LOG = 0xA4

class RSP:
    VALUE_P_T = 0x17
    VALUE_H_T = 0x18
    COEFF_P = 0x14
    COEFF_T = 0x19
    COEFF_H = 0x1A
    TIME_T = 0x15
    DATETIME = 0x20
    DEVICE_INFO = 0x23
    DEVICE_VERSION = 0x24
    LOG_SIZE = 0xB0
    LOG_RECORD = 0xB1
    LOG_READ_COMPLETE = 0xB5

# ==================== ГЛАВНОЕ ПРИЛОЖЕНИЕ ====================

class MeteorStationApp(App):
    connection_status = StringProperty("Отключено")
    device_name = StringProperty("Метеостанция")
    
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
    
    log_size = StringProperty("0")
    
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
        
        status_layout = BoxLayout(orientation='vertical', size_hint=(0.5, 1))
        status_layout.add_widget(Label(
            text=f'Статус: {self.connection_status}',
            font_size='14sp',
            halign='left'
        ))
        status_layout.add_widget(Label(
            text=f'Устройство: {self.device_name}',
            font_size='12sp',
            halign='left'
        ))
        
        btn_layout = BoxLayout(size_hint=(0.5, 1), spacing=dp(5))
        
        self.scan_btn = Button(
            text='Сканировать',
            font_size='12sp',
            on_press=self.scan_devices
        )
        
        self.connect_btn = Button(
            text='Подключиться',
            font_size='12sp',
            disabled=True,
            on_press=self.toggle_connection
        )
        
        btn_layout.add_widget(self.scan_btn)
        btn_layout.add_widget(self.connect_btn)
        
        panel.add_widget(status_layout)
        panel.add_widget(btn_layout)
        
        return panel
    
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
        btn_layout.add_widget(Button(
            text='Давление/Темп',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.GET_VALUE_P_T)
        ))
        btn_layout.add_widget(Button(
            text='Влажность',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.GET_VALUE_H_T)
        ))
        
        layout.add_widget(Label(text=''))
        layout.add_widget(btn_layout)
        
        return layout
    
    def create_coeff_tab(self):
        layout = GridLayout(cols=2, spacing=dp(20), padding=dp(20), size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))
        
        # Канал P
        layout.add_widget(Label(text='Канал P (давление):', font_size='16sp', bold=True, size_hint_y=None, height=dp(45)))
        layout.add_widget(Label(text=''))
        
        layout.add_widget(Label(text='Коэф. A:', size_hint_y=None, height=dp(40)))
        self.coeff_p_a_input = TextInput(text=self.coeff_p_a, multiline=False, size_hint_y=None, height=dp(40))
        layout.add_widget(self.coeff_p_a_input)
        
        layout.add_widget(Label(text='Коэф. B:', size_hint_y=None, height=dp(40)))
        self.coeff_p_b_input = TextInput(text=self.coeff_p_b, multiline=False, size_hint_y=None, height=dp(40))
        layout.add_widget(self.coeff_p_b_input)
        
        btn_p_layout = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(15))
        btn_p_layout.add_widget(Button(
            text='Прочитать P',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.GET_COEFF_P)
        ))
        btn_p_layout.add_widget(Button(
            text='Записать P',
            font_size='12sp',
            on_press=self.set_coeff_p
        ))
        layout.add_widget(Label(text=''))
        layout.add_widget(btn_p_layout)
        
        layout.add_widget(Widget(size_hint_y=None, height=dp(15)))
        layout.add_widget(Widget(size_hint_y=None, height=dp(15)))
        
        # Канал T
        layout.add_widget(Label(text='Канал T (температура):', font_size='16sp', bold=True, size_hint_y=None, height=dp(45)))
        layout.add_widget(Label(text=''))
        
        layout.add_widget(Label(text='Коэф. A:', size_hint_y=None, height=dp(40)))
        self.coeff_t_a_input = TextInput(text=self.coeff_t_a, multiline=False, size_hint_y=None, height=dp(40))
        layout.add_widget(self.coeff_t_a_input)
        
        layout.add_widget(Label(text='Коэф. B:', size_hint_y=None, height=dp(40)))
        self.coeff_t_b_input = TextInput(text=self.coeff_t_b, multiline=False, size_hint_y=None, height=dp(40))
        layout.add_widget(self.coeff_t_b_input)
        
        btn_t_layout = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(15))
        btn_t_layout.add_widget(Button(
            text='Прочитать T',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.GET_COEFF_T)
        ))
        btn_t_layout.add_widget(Button(
            text='Записать T',
            font_size='12sp',
            on_press=self.set_coeff_t
        ))
        layout.add_widget(Label(text=''))
        layout.add_widget(btn_t_layout)
        
        layout.add_widget(Widget(size_hint_y=None, height=dp(15)))
        layout.add_widget(Widget(size_hint_y=None, height=dp(15)))
        
        # Канал H
        layout.add_widget(Label(text='Канал H (влажность):', font_size='16sp', bold=True, size_hint_y=None, height=dp(45)))
        layout.add_widget(Label(text=''))
        
        layout.add_widget(Label(text='Коэф. A:', size_hint_y=None, height=dp(40)))
        self.coeff_h_a_input = TextInput(text=self.coeff_h_a, multiline=False, size_hint_y=None, height=dp(40))
        layout.add_widget(self.coeff_h_a_input)
        
        layout.add_widget(Label(text='Коэф. B:', size_hint_y=None, height=dp(40)))
        self.coeff_h_b_input = TextInput(text=self.coeff_h_b, multiline=False, size_hint_y=None, height=dp(40))
        layout.add_widget(self.coeff_h_b_input)
        
        btn_h_layout = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(15))
        btn_h_layout.add_widget(Button(
            text='Прочитать H',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.GET_COEFF_H)
        ))
        btn_h_layout.add_widget(Button(
            text='Записать H',
            font_size='12sp',
            on_press=self.set_coeff_h
        ))
        layout.add_widget(Label(text=''))
        layout.add_widget(btn_h_layout)
        
        return layout
    
    def create_settings_tab(self):
        layout = GridLayout(cols=2, spacing=dp(20), padding=dp(20), size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))
        
        # Период измерений
        layout.add_widget(Label(text='Период измерений:', font_size='16sp', bold=True, size_hint_y=None, height=dp(45)))
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
        layout.add_widget(Label(text='Дата и время:', font_size='16sp', bold=True, size_hint_y=None, height=dp(45)))
        layout.add_widget(Label(text=''))
        
        layout.add_widget(Label(text='На устройстве:', size_hint_y=None, height=dp(40)))
        layout.add_widget(Label(text=self.device_time, size_hint_y=None, height=dp(40)))
        
        btn_sync_layout = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(15))
        btn_sync_layout.add_widget(Button(
            text='Прочитать',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.GET_DATETIME)
        ))
        btn_sync_layout.add_widget(Button(
            text='Синхронизировать',
            font_size='12sp',
            on_press=self.sync_datetime
        ))
        layout.add_widget(Label(text=''))
        layout.add_widget(btn_sync_layout)
        
        return layout
    
    def create_log_tab(self):
        layout = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(10))
        
        control_panel = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        control_panel.add_widget(Button(
            text='Размер журнала',
            font_size='12sp',
            on_press=lambda x: self.send_command(CMD.GET_LOG_SIZE)
        ))
        control_panel.add_widget(Button(
            text='Читать журнал',
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
        
        layout.add_widget(Label(text='Версия прошивки:', font_size='16sp', size_hint_y=None, height=dp(50)))
        layout.add_widget(Label(text=self.firmware_version, font_size='16sp', size_hint_y=None, height=dp(50)))
        
        layout.add_widget(Label(text='Серийный номер:', font_size='16sp', size_hint_y=None, height=dp(50)))
        layout.add_widget(Label(text=self.serial_number, font_size='16sp', size_hint_y=None, height=dp(50)))
        
        layout.add_widget(Label(text='Дата производства:', font_size='16sp', size_hint_y=None, height=dp(50)))
        layout.add_widget(Label(text='---', font_size='16sp', size_hint_y=None, height=dp(50)))
        
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(15))
        btn_layout.add_widget(Button(
            text='Информация',
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
        # Здесь будет сканирование
        Clock.schedule_once(lambda dt: self.scan_complete(), 2)
    
    def scan_complete(self):
        self.scan_btn.text = 'Сканировать'
        self.scan_btn.disabled = False
        self.connect_btn.disabled = False
        self.device_name = "Метеостанция-01"
    
    def toggle_connection(self, instance):
        if not hasattr(self, 'connected') or not self.connected:
            self.connect_btn.text = 'Подключение...'
            self.connect_btn.disabled = True
            Clock.schedule_once(lambda dt: self.connect_complete(), 1)
        else:
            self.connected = False
            self.connection_status = "Отключено"
            self.connect_btn.text = 'Подключиться'
    
    def connect_complete(self):
        self.connected = True
        self.connection_status = "Подключено"
        self.connect_btn.text = 'Отключиться'
        self.connect_btn.disabled = False
        self.scan_btn.disabled = True
    
    def send_command(self, cmd):
        print(f"Отправка команды: {hex(cmd)}")
        return True
    
    def set_coeff_p(self, instance):
        try:
            a = float(self.coeff_p_a_input.text)
            b = float(self.coeff_p_b_input.text)
            print(f"Установка P: A={a}, B={b}")
            self.show_message('Коэффициенты P отправлены')
        except ValueError:
            self.show_popup('Ошибка', 'Введите числа')
    
    def set_coeff_t(self, instance):
        try:
            a = float(self.coeff_t_a_input.text)
            b = float(self.coeff_t_b_input.text)
            print(f"Установка T: A={a}, B={b}")
            self.show_message('Коэффициенты T отправлены')
        except ValueError:
            self.show_popup('Ошибка', 'Введите числа')
    
    def set_coeff_h(self, instance):
        try:
            a = float(self.coeff_h_a_input.text)
            b = float(self.coeff_h_b_input.text)
            print(f"Установка H: A={a}, B={b}")
            self.show_message('Коэффициенты H отправлены')
        except ValueError:
            self.show_popup('Ошибка', 'Введите числа')
    
    def set_measurement_period(self, instance):
        try:
            period = int(self.period_input.text)
            print(f"Установка периода: {period} мс")
            self.show_message(f'Период: {period} мс')
        except ValueError:
            self.show_popup('Ошибка', 'Введите число')
    
    def sync_datetime(self, instance):
        timestamp = int(time.time())
        print(f"Синхронизация времени: {timestamp}")
        self.show_message('Время синхронизировано')
    
    def start_read_log(self, instance):
        print("Начало чтения журнала")
        self.show_message('Чтение журнала...')
    
    def show_popup(self, title, message):
        content = BoxLayout(orientation='vertical', padding=dp(10))
        content.add_widget(Label(text=message))
        btn = Button(text='OK', size_hint_y=None, height=dp(40))
        content.add_widget(btn)
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.4))
        btn.bind(on_press=popup.dismiss)
        popup.open()
    
    def show_message(self, message):
        print(message)

if __name__ == '__main__':
    MeteorStationApp().run()
