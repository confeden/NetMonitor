import tkinter as tk
import time
import threading
import json
import os
import sys
import socket
import winreg  # Модуль для работы с реестром
import ctypes

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
TRANS_COLOR = "#000001" # Технический цвет для прозрачности
WINDOW_ALPHA = 0.7

CONFIG_FILE = "pos_config.json"
APP_NAME = "NetMonitorUtility" # Имя ключа в реестре

# --- ОСНОВНОЕ ПРИЛОЖЕНИЕ ---
class NetMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NetMonitor")

        # --- ФОНОВОЕ ОКНО (ROOT) ---
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG_COLOR)

        # --- ТЕКСТОВОЕ ОКНО (FRONT) ---
        self.front = tk.Toplevel(self.root)
        self.front.overrideredirect(True)
        self.front.attributes("-topmost", True)
        self.front.attributes("-transparentcolor", TRANS_COLOR)
        self.front.configure(bg=TRANS_COLOR)

        self.alpha = WINDOW_ALPHA # Значение по умолчанию
        self.label = tk.Label(self.front, text="...", font=FONT_CONFIG, fg=COLOR_ONLINE, bg=TRANS_COLOR, padx=8, pady=2)
        self.label.pack()

        self.front.bind("<Configure>", self.sync_windows)
        self.load_position()

        # Бинды
        for widget in (self.root, self.label):
            widget.bind("<Button-1>", self.start_move)
            widget.bind("<B1-Motion>", self.do_move)
            widget.bind("<ButtonRelease-1>", self.stop_move)
            widget.bind("<Button-3>", self.show_menu) # ПКМ

        # Создаем меню (пункты будут добавляться динамически)
        self.menu = tk.Menu(self.root, tearoff=0)

        self.running = True
        threading.Thread(target=self.worker_loop, daemon=True).start()
        self.keep_on_top()

    def load_position(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                d = json.load(f)
                geom = f"+{d['x']}+{d['y']}"
                self.root.geometry(geom)
                self.front.geometry(geom)
                self.alpha = d.get("alpha", WINDOW_ALPHA)
        except:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            geom = f"+{sw - 450}+{sh - 40}"
            self.root.geometry(geom)
            self.front.geometry(geom)
            self.alpha = WINDOW_ALPHA
        self.root.attributes("-alpha", self.alpha)

    def sync_windows(self, e=None):
        """Синхронизирует размер и позицию фона с текстом"""
        if self.front.winfo_exists():
            self.root.geometry(f"{self.front.winfo_width()}x{self.front.winfo_height()}+{self.front.winfo_x()}+{self.front.winfo_y()}")

    def save_position(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump({"x": self.front.winfo_x(), "y": self.front.winfo_y(), "alpha": self.alpha}, f)
        except: pass

    def start_move(self, e): self.x, self.y = e.x, e.y
    def do_move(self, e): 
        new_x = self.front.winfo_x() + e.x - self.x
        new_y = self.front.winfo_y() + e.y - self.y
        geom = f"+{new_x}+{new_y}"
        self.root.geometry(geom)
        self.front.geometry(geom)
    def stop_move(self, e): self.save_position()

    # --- ЛОГИКА МЕНЮ ---
    def show_menu(self, e):
        self.menu_x = e.x_root # Запоминаем координату X открытия меню
        # Очищаем старое меню перед показом
        self.menu.delete(0, 'end')
        
        # Проверяем статус автозапуска
        is_enabled = False
        cmd = f'"{sys.executable}"' if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ) as key:
                if winreg.QueryValueEx(key, APP_NAME)[0] == cmd: is_enabled = True
        except: pass
            
        # Добавляем пункты
        self.menu.add_command(label="Выкл. автозапуск" if is_enabled else "Вкл. автозапуск", command=self.toggle_startup)
        self.menu.add_command(label="Прозрачность", command=self.show_opacity_slider)
        self.menu.add_separator()
        self.menu.add_command(label="Закрыть", command=self.root.quit)
        
        # Показываем меню
        self.menu.post(e.x_root, e.y_root)

    def show_opacity_slider(self):
        # Создаем всплывающее окно для слайдера
        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg=BG_COLOR)
        
        # Позиционируем рядом с курсором
        x, y = self.root.winfo_pointerxy()
        top.geometry(f"200x32+{getattr(self, 'menu_x', x)}+{y-16}")
        
        # Слайдер
        s = tk.Scale(top, from_=0.1, to=1.0, resolution=0.05, orient=tk.HORIZONTAL,
                     bg=BG_COLOR, fg=COLOR_ONLINE, troughcolor="#444", activebackground=COLOR_ONLINE,
                     highlightthickness=0, bd=0, width=30, sliderlength=20, showvalue=0, command=self.set_alpha)
        s.set(self.alpha)
        s.pack(fill="both", expand=True)
        
        # Закрываем при потере фокуса (клик вне окна)
        s.focus_set()
        top.bind("<FocusOut>", lambda e: [self.save_position(), top.destroy()])
        top.bind("<Escape>", lambda e: top.destroy())

    def toggle_startup(self):
        cmd = f'"{sys.executable}"' if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
            try:
                winreg.QueryValueEx(key, APP_NAME)
                winreg.DeleteValue(key, APP_NAME) # Если ключ есть - удаляем
            except FileNotFoundError:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd) # Если нет - создаем
            winreg.CloseKey(key)
        except Exception as e: print(f"Reg err: {e}")

    def set_alpha(self, val):
        self.alpha = float(val)
        self.root.attributes("-alpha", self.alpha)

    def keep_on_top(self):
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.front.lift()
        self.front.attributes("-topmost", True)
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
            start = time.time()
            # Оптимизация: используем socket вместо urllib для уменьшения размера exe
            parts = HTTP_URL.split("/")
            host = parts[2]
            path = "/" + "/".join(parts[3:])
            
            with socket.create_connection((host, 80), timeout=1.5) as s:
                request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
                s.sendall(request.encode())
                resp = s.recv(128) # Читаем только начало ответа
                if b"HTTP/1.1 204" in resp:
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
    # Проверка на повторный запуск (Singleton)
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, "NetMonitorUtility_Mutex")
    if kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
        sys.exit(0)

    root = tk.Tk()
    app = NetMonitorApp(root)
    root.mainloop()