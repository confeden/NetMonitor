import tkinter as tk
import time
import threading
import json
import os
import sys
import socket
import importlib.util
import subprocess
import winreg  # Модуль для работы с реестром

# --- КОНФИГУРАЦИЯ ---
PING_HOST = "8.8.8.8"
PING_PORT = 53
HTTP_URL = "http://connectivitycheck.gstatic.com/generate_204"

CHECK_INTERVAL = 1.0
FONT_CONFIG = ("Segoe UI", 12, "bold")

# ЦВЕТА
COLOR_ONLINE = "#34e77e"
COLOR_SLOW = "#e7da34"
COLOR_OFFLINE = "#e74734"
BG_COLOR = "#101010"
WINDOW_ALPHA = 0.7

CONFIG_FILE = "pos_config.json"
APP_NAME = "NetMonitorUtility" # Имя ключа в реестре

# --- МЕНЕДЖЕР АВТОЗАПУСКА ---
class StartupManager:
    def __init__(self):
        self.reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def _get_run_command(self):
        """Определяет правильную команду для запуска (exe или скрипт)"""
        if getattr(sys, 'frozen', False):
            # Если запущено как .exe (PyInstaller)
            return f'"{sys.executable}"'
        else:
            # Если запущено как .py/.pyw
            # pythonw.exe "путь_к_скрипту"
            script = os.path.abspath(sys.argv[0])
            return f'"{sys.executable}" "{script}"'

    def is_enabled(self):
        """Проверяет, включен ли автозапуск"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_path, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            # Проверяем, совпадает ли текущий путь с тем, что в реестре
            return value == self._get_run_command()
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def toggle(self):
        """Включает или выключает автозапуск"""
        if self.is_enabled():
            self._remove()
            return False # Теперь выключено
        else:
            self._add()
            return True # Теперь включено

    def _add(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, self._get_run_command())
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Err add startup: {e}")

    def _remove(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_path, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, APP_NAME)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Err remove startup: {e}")

# --- УСТАНОВЩИК ЗАВИСИМОСТЕЙ ---
class DependencyInstaller:
    def __init__(self, root, package_name):
        self.root = root
        self.package = package_name
        self.root.title("Setup")
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        self.root.geometry(f"300x80+{(sw-300)//2}+{(sh-80)//2}")
        self.root.overrideredirect(True)
        self.root.configure(bg=BG_COLOR)
        self.root.attributes("-topmost", True)
        tk.Label(root, text=f"Установка: {package_name}...", font=("Segoe UI", 10), 
                 fg=COLOR_ONLINE, bg=BG_COLOR).pack(expand=True)
        threading.Thread(target=self.install, daemon=True).start()

    def install(self):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", self.package],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.root.after(100, self.root.destroy)
        except:
            self.root.after(2000, self.root.destroy)

# --- ОСНОВНОЕ ПРИЛОЖЕНИЕ ---
class NetMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NetMonitor")
        
        self.session = None 
        self.startup_mgr = StartupManager() # Подключаем менеджер

        # GUI Setup
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", WINDOW_ALPHA)
        self.root.configure(bg=BG_COLOR)

        self.label = tk.Label(root, text="...", font=FONT_CONFIG, fg=COLOR_ONLINE, bg=BG_COLOR, padx=8, pady=2)
        self.label.pack()

        self.load_position()

        # Бинды
        self.label.bind("<Button-1>", self.start_move)
        self.label.bind("<B1-Motion>", self.do_move)
        self.label.bind("<ButtonRelease-1>", self.stop_move)
        self.label.bind("<Button-3>", self.show_menu) # ПКМ

        # Создаем меню (пункты будут добавляться динамически)
        self.menu = tk.Menu(self.root, tearoff=0)

        self.running = True
        threading.Thread(target=self.worker_loop, daemon=True).start()
        self.keep_on_top()

    def load_position(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                d = json.load(f)
                self.root.geometry(f"+{d['x']}+{d['y']}")
        except:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.root.geometry(f"+{sw - 450}+{sh - 40}")

    def save_position(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump({"x": self.root.winfo_x(), "y": self.root.winfo_y()}, f)
        except: pass

    def start_move(self, e): self.x, self.y = e.x, e.y
    def do_move(self, e): 
        self.root.geometry(f"+{self.root.winfo_x() + e.x - self.x}+{self.root.winfo_y() + e.y - self.y}")
    def stop_move(self, e): self.save_position()

    # --- ЛОГИКА МЕНЮ ---
    def show_menu(self, e):
        # Очищаем старое меню перед показом
        self.menu.delete(0, 'end')
        
        # Проверяем статус автозапуска
        if self.startup_mgr.is_enabled():
            label_text = "Выкл. автозапуск"
        else:
            label_text = "Вкл. автозапуск"
            
        # Добавляем пункты
        self.menu.add_command(label=label_text, command=self.toggle_startup)
        self.menu.add_separator()
        self.menu.add_command(label="Закрыть", command=self.root.quit)
        
        # Показываем меню
        self.menu.post(e.x_root, e.y_root)

    def toggle_startup(self):
        self.startup_mgr.toggle()

    def keep_on_top(self):
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(3000, self.keep_on_top)

    def fast_tcp_ping(self):
        try:
            start = time.time()
            with socket.create_connection((PING_HOST, PING_PORT), timeout=1):
                pass
            return int((time.time() - start) * 1000)
        except (socket.timeout, socket.error):
            return None

    def http_check(self):
        try:
            if self.session is None:
                import requests
                self.session = requests.Session()
            start = time.time()
            resp = self.session.get(HTTP_URL, timeout=1.5, stream=True)
            if resp.status_code == 204:
                return int((time.time() - start) * 1000)
            return None
        except:
            return None

    def worker_loop(self):
        while self.running:
            ms = self.fast_tcp_ping()
            mode = "Ping"
            if ms is None:
                ms = self.http_check()
                mode = "VPN"
                if ms is None:
                    mode = "OFFLINE"

            if mode == "OFFLINE":
                text, color = "OFFLINE", COLOR_OFFLINE
            else:
                text = f"{mode}: {ms}"
                if ms < 150: color = COLOR_ONLINE
                elif ms < 300: color = COLOR_SLOW
                else: color = COLOR_OFFLINE
            
            try:
                self.root.after(0, lambda t=text, c=color: self.label.config(text=t, fg=c))
            except: 
                break
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    REQ = "requests"
    if importlib.util.find_spec(REQ) is None:
        tr = tk.Tk()
        DependencyInstaller(tr, REQ)
        tr.mainloop()
    try:
        import requests 
        root = tk.Tk()
        app = NetMonitorApp(root)
        root.mainloop()
    except ImportError: pass