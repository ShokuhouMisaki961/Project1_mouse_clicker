import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import time
import os
import sys
import shutil
import pyautogui
from pynput import keyboard, mouse
import json
import ctypes

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True  # 鼠标移到左上角紧急停止

def get_config_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), "clicker_config.json")
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "clicker_config.json")

CONFIG_FILE = get_config_path()

DEFAULT_CONFIG = {
    "hotkey_start": "<f6>",
    "hotkey_stop": "<f7>",
    "hotkey_capture": "<f8>",
    "interval": "100",
    "button": "left",
    "times": "0",
    "use_pos": False,
    "pos_x": "0",
    "pos_y": "0",
    "topmost": True,
    "smart_pause": True,
    "return_mouse": True,
    "win_width": 480,
    "win_height": 780,
    "macros": {},
    "macro_loop_count": "1"
}

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000

class MouseClicker:
    def __init__(self, root):
        self.root = root
        self.root.title("鼠标连点器 - 宏录制版")

        # 先初始化默认配置
        self.config = DEFAULT_CONFIG.copy()
        try:
            loaded = self.load_config()
            if loaded:
                self.config = loaded
        except:
            pass

        w = int(self.config.get("win_width", 480))
        h = int(self.config.get("win_height", 780))
        self.root.geometry(f"{w}x{h}")
        self.root.minsize(420, 700)
        self.root.resizable(True, True)

        # 连点状态
        self.stop_event = threading.Event()
        self.stop_event.set()
        self.click_thread = None
        self.click_count = 0
        self.target_x = None
        self.target_y = None
        self.listener = None
        self.paused = False

        # 宏录制状态
        self.is_recording = False
        self.macro_events = []
        self.last_event_time = 0
        self.mouse_listener = None
        self.keyboard_listener = None
        self.macro_play_thread = None
        self.macro_stop_event = threading.Event()
        self.macro_stop_event.set()
        self.current_macro_name = ""

        self.root.attributes("-topmost", self.config["topmost"])
        self.build_ui()
        self.start_hotkey_listener()
        self.refresh_macro_list()

        self.root.bind("<Configure>", self.on_window_resize)

    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    merged = DEFAULT_CONFIG.copy()
                    merged.update(cfg)
                    return merged
        except:
            pass
        return None

    def save_config(self):
        try:
            self.config["interval"] = self.interval_var.get()
            self.config["button"] = self.button_var.get()
            self.config["times"] = self.times_var.get()
            self.config["use_pos"] = self.use_pos_var.get()
            self.config["pos_x"] = self.pos_x_var.get()
            self.config["pos_y"] = self.pos_y_var.get()
            self.config["topmost"] = self.topmost_var.get()
            self.config["smart_pause"] = self.smart_pause_var.get()
            self.config["return_mouse"] = self.return_mouse_var.get()
            self.config["macro_loop_count"] = self.macro_loop_var.get()
            self.config["win_width"] = self.root.winfo_width()
            self.config["win_height"] = self.root.winfo_height()
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except:
            pass

    def on_window_resize(self, event):
        if event.widget == self.root:
            if hasattr(self, '_resize_timer'):
                self.root.after_cancel(self._resize_timer)
            self._resize_timer = self.root.after(500, self.save_config)

    def build_ui(self):
        # 主容器 + 滚动条
        main_canvas = tk.Canvas(self.root, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        main_frame = ttk.Frame(main_canvas, padding=10)

        main_frame.bind("<Configure>", 
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")))
        main_canvas.create_window((0, 0), window=main_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 鼠标滚轮滚动
        def on_mousewheel(e):
            main_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        main_canvas.bind_all("<MouseWheel>", on_mousewheel)

        # ===== 标题 =====
        title_label = ttk.Label(main_frame, text="鼠标连点器", font=("微软雅黑", 16, "bold"))
        title_label.pack(pady=8)

        # ===== 基础连点设置 =====
        setting_frame = ttk.LabelFrame(main_frame, text="基础连点设置", padding=10)
        setting_frame.pack(fill="x", pady=5)

        row1 = ttk.Frame(setting_frame)
        row1.pack(fill="x", pady=3)
        ttk.Label(row1, text="点击间隔(毫秒):", width=14).pack(side="left")
        self.interval_var = tk.StringVar(value=self.config["interval"])
        ttk.Entry(row1, textvariable=self.interval_var, width=10).pack(side="left")

        row2 = ttk.Frame(setting_frame)
        row2.pack(fill="x", pady=3)
        ttk.Label(row2, text="点击按键:", width=14).pack(side="left")
        self.button_var = tk.StringVar(value=self.config["button"])
        ttk.Radiobutton(row2, text="左键", variable=self.button_var, value="left").pack(side="left", padx=5)
        ttk.Radiobutton(row2, text="右键", variable=self.button_var, value="right").pack(side="left", padx=5)

        row3 = ttk.Frame(setting_frame)
        row3.pack(fill="x", pady=3)
        ttk.Label(row3, text="点击次数(0=无限):", width=14).pack(side="left")
        self.times_var = tk.StringVar(value=self.config["times"])
        ttk.Entry(row3, textvariable=self.times_var, width=10).pack(side="left")

        # ===== 窗口设置 =====
        win_frame = ttk.LabelFrame(main_frame, text="窗口设置", padding=10)
        win_frame.pack(fill="x", pady=5)

        self.topmost_var = tk.BooleanVar(value=self.config["topmost"])
        ttk.Checkbutton(win_frame, text="窗口置顶（切换游戏/软件时仍可见）", 
                        variable=self.topmost_var, 
                        command=self.toggle_topmost).pack(anchor="w", pady=2)

        ttk.Label(win_frame, text="💡 拖动窗口边缘可自由缩放，内容过多可滚动鼠标", 
                  foreground="gray", font=("微软雅黑", 9)).pack(anchor="w", pady=2)

        # ===== 固定坐标 =====
        pos_frame = ttk.LabelFrame(main_frame, text="固定坐标点击", padding=10)
        pos_frame.pack(fill="x", pady=5)

        self.use_pos_var = tk.BooleanVar(value=self.config["use_pos"])
        ttk.Checkbutton(pos_frame, text="启用固定坐标点击", 
                        variable=self.use_pos_var).pack(anchor="w", pady=2)

        row4 = ttk.Frame(pos_frame)
        row4.pack(fill="x", pady=3)
        ttk.Label(row4, text="X坐标:", width=8).pack(side="left")
        self.pos_x_var = tk.StringVar(value=self.config["pos_x"])
        ttk.Entry(row4, textvariable=self.pos_x_var, width=8).pack(side="left", padx=2)
        ttk.Label(row4, text=" Y坐标:", width=8).pack(side="left")
        self.pos_y_var = tk.StringVar(value=self.config["pos_y"])
        ttk.Entry(row4, textvariable=self.pos_y_var, width=8).pack(side="left", padx=2)

        ttk.Button(pos_frame, text="获取当前鼠标坐标 (" + self.format_hotkey(self.config["hotkey_capture"]) + ")", 
                   command=self.capture_position).pack(pady=5, anchor="w")

        self.return_mouse_var = tk.BooleanVar(value=self.config["return_mouse"])
        ttk.Checkbutton(pos_frame, text="点击后鼠标归位", 
                        variable=self.return_mouse_var).pack(anchor="w", pady=2)

        self.smart_pause_var = tk.BooleanVar(value=self.config["smart_pause"])
        ttk.Checkbutton(pos_frame, text="✨ 智能防打扰（移动鼠标自动暂停）", 
                        variable=self.smart_pause_var).pack(anchor="w", pady=2)

        # ===== 宏录制区 =====
        macro_frame = ttk.LabelFrame(main_frame, text="🎬 宏录制与回放", padding=10)
        macro_frame.pack(fill="x", pady=5)

        # 录制控制
        rec_row = ttk.Frame(macro_frame)
        rec_row.pack(fill="x", pady=3)
        self.record_btn = ttk.Button(rec_row, text="● 开始录制", command=self.toggle_record, width=14)
        self.record_btn.pack(side="left", padx=3)
        self.macro_status_label = ttk.Label(rec_row, text="就绪", foreground="gray", font=("微软雅黑", 9))
        self.macro_status_label.pack(side="left", padx=10)

        # 宏选择
        sel_row = ttk.Frame(macro_frame)
        sel_row.pack(fill="x", pady=3)
        ttk.Label(sel_row, text="选择宏:", width=8).pack(side="left")
        self.macro_combo = ttk.Combobox(sel_row, state="readonly", width=18)
        self.macro_combo.pack(side="left", padx=2)
        ttk.Button(sel_row, text="删除", command=self.delete_macro, width=6).pack(side="left", padx=3)

        # 循环次数
        loop_row = ttk.Frame(macro_frame)
        loop_row.pack(fill="x", pady=3)
        ttk.Label(loop_row, text="循环次数:", width=8).pack(side="left")
        self.macro_loop_var = tk.StringVar(value=self.config.get("macro_loop_count", "1"))
        ttk.Entry(loop_row, textvariable=self.macro_loop_var, width=8).pack(side="left", padx=2)
        ttk.Label(loop_row, text="(0=无限循环)", foreground="gray", font=("微软雅黑", 9)).pack(side="left", padx=5)

        # 播放控制
        play_row = ttk.Frame(macro_frame)
        play_row.pack(pady=5)
        self.play_btn = ttk.Button(play_row, text="▶ 播放宏", command=self.play_macro, width=12)
        self.play_btn.grid(row=0, column=0, padx=5)
        self.stop_play_btn = ttk.Button(play_row, text="■ 停止播放", command=self.stop_macro, width=12, state="disabled")
        self.stop_play_btn.grid(row=0, column=1, padx=5)

        ttk.Label(macro_frame, text="录制内容：鼠标点击/移动 + 键盘按键\n提示：录制时按 ESC 结束录制", 
                  foreground="gray", font=("微软雅黑", 9), justify="left").pack(anchor="w", pady=3)

        # ===== 状态区 =====
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill="both", expand=True, pady=5)

        self.status_label = ttk.Label(status_frame, text="状态：已停止", 
                                      foreground="red", font=("微软雅黑", 11, "bold"))
        self.status_label.pack(pady=5)

        self.count_label = ttk.Label(status_frame, text="已点击：0 次", 
                                     foreground="gray", font=("微软雅黑", 10))
        self.count_label.pack()

        self.pause_label = ttk.Label(status_frame, text="", 
                                     foreground="orange", font=("微软雅黑", 9))
        self.pause_label.pack()

        # ===== 主按钮 =====
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=5)
        self.start_btn = ttk.Button(btn_frame, text="开始连点 (" + self.format_hotkey(self.config["hotkey_start"]) + ")", 
                                    command=self.start_clicking, width=18)
        self.start_btn.grid(row=0, column=0, padx=6)
        self.stop_btn = ttk.Button(btn_frame, text="停止连点 (" + self.format_hotkey(self.config["hotkey_stop"]) + ")", 
                                   command=self.stop_clicking, width=18, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=6)

        # ===== 底部功能 =====
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(pady=5)
        ttk.Button(bottom_frame, text="⚙ 修改快捷键", command=self.open_hotkey_settings, width=14).grid(row=0, column=0, padx=5)
        ttk.Button(bottom_frame, text="🗑 一键卸载", command=self.uninstall, width=14).grid(row=0, column=1, padx=5)

        tip_label = ttk.Label(main_frame, 
            text="紧急停止：将鼠标快速移到屏幕左上角\n（pyautogui 安全机制）",
            foreground="gray", font=("微软雅黑", 9), justify="center")
        tip_label.pack(pady=8, side="bottom")

    # ========== 宏录制功能 ==========

    def toggle_record(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self.is_recording = True
        self.macro_events = []
        self.last_event_time = time.time()
        self.record_btn.config(text="■ 结束录制")
        self.macro_status_label.config(text="录制中... 按ESC结束", foreground="red")

        # 启动鼠标监听
        self.mouse_listener = mouse.Listener(
            on_click=self.on_macro_click,
            on_move=self.on_macro_move
        )
        self.mouse_listener.start()

        # 启动键盘监听（ESC停止）
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_macro_key
        )
        self.keyboard_listener.start()

    def stop_recording(self):
        self.is_recording = False
        self.record_btn.config(text="● 开始录制")
        self.macro_status_label.config(text=f"录制完成，共 {len(self.macro_events)} 个动作", foreground="green")

        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None

        # 保存宏
        if self.macro_events:
            name = simpledialog.askstring("保存宏", "请输入宏名称：", parent=self.root)
            if name:
                self.config.setdefault("macros", {})[name] = self.macro_events
                self.save_config()
                self.refresh_macro_list()
                self.macro_combo.set(name)
                messagebox.showinfo("成功", f"宏「{name}」已保存！")

    def on_macro_click(self, x, y, button, pressed):
        """录制鼠标点击"""
        if not self.is_recording:
            return
        if pressed:  # 只记录按下瞬间
            now = time.time()
            delay = now - self.last_event_time
            self.last_event_time = now
            btn = "left" if button == mouse.Button.left else "right"
            self.macro_events.append({
                "type": "click",
                "x": int(x),
                "y": int(y),
                "button": btn,
                "delay": round(delay, 3)
            })
            self.root.after(0, lambda: self.macro_status_label.config(
                text=f"录制中... {len(self.macro_events)} 个动作", foreground="red"))

    def on_macro_move(self, x, y):
        """录制鼠标移动（降采样，避免事件太多）"""
        if not self.is_recording:
            return
        # 每隔一定时间记录一次移动，防止数据量太大
        now = time.time()
        if now - self.last_event_time >= 0.05:  # 50ms采样一次
            delay = now - self.last_event_time
            self.last_event_time = now
            self.macro_events.append({
                "type": "move",
                "x": int(x),
                "y": int(y),
                "delay": round(delay, 3)
            })

    def on_macro_key(self, key):
        """录制键盘按键"""
        if not self.is_recording:
            return
        # ESC 停止录制
        if key == keyboard.Key.esc:
            self.root.after(0, self.stop_recording)
            return

        now = time.time()
        delay = now - self.last_event_time
        self.last_event_time = now

        try:
            key_str = key.char
        except AttributeError:
            key_str = str(key).replace("Key.", "")

        self.macro_events.append({
            "type": "keypress",
            "key": key_str,
            "delay": round(delay, 3)
        })
        self.root.after(0, lambda: self.macro_status_label.config(
            text=f"录制中... {len(self.macro_events)} 个动作", foreground="red"))

    def refresh_macro_list(self):
        macros = self.config.get("macros", {})
        self.macro_combo['values'] = list(macros.keys())
        if macros and not self.macro_combo.get():
            self.macro_combo.current(0)

    def delete_macro(self):
        name = self.macro_combo.get()
        if not name:
            return
        if messagebox.askyesno("确认", f"删除宏「{name}」？"):
            self.config.get("macros", {}).pop(name, None)
            self.save_config()
            self.refresh_macro_list()
            self.macro_status_label.config(text=f"已删除 {name}", foreground="gray")

    def play_macro(self):
        name = self.macro_combo.get()
        if not name:
            messagebox.showwarning("提示", "请先选择一个宏")
            return
        macros = self.config.get("macros", {})
        events = macros.get(name)
        if not events:
            messagebox.showwarning("提示", "宏内容为空")
            return

        try:
            loop_count = max(0, int(self.macro_loop_var.get()))
        except ValueError:
            messagebox.showerror("错误", "循环次数请输入数字")
            return

        self.current_macro_name = name
        self.macro_stop_event.clear()
        self.play_btn.config(state="disabled")
        self.stop_play_btn.config(state="normal")
        self.macro_status_label.config(text=f"播放中：{name}", foreground="blue")

        self.macro_play_thread = threading.Thread(
            target=self._play_macro_loop, args=(events, loop_count), daemon=True)
        self.macro_play_thread.start()

    def stop_macro(self):
        self.macro_stop_event.set()
        self.play_btn.config(state="normal")
        self.stop_play_btn.config(state="disabled")
        self.macro_status_label.config(text="播放已停止", foreground="gray")

    def _play_macro_loop(self, events, loop_count):
        loop = 0
        while not self.macro_stop_event.is_set():
            if loop_count > 0 and loop >= loop_count:
                break
            loop += 1

            for evt in events:
                if self.macro_stop_event.is_set():
                    break

                # 等待延迟（分片，响应停止更快）
                delay = evt.get("delay", 0.1)
                waited = 0
                while waited < delay and not self.macro_stop_event.is_set():
                    chunk = min(delay - waited, 0.02)
                    time.sleep(chunk)
                    waited += chunk

                if self.macro_stop_event.is_set():
                    break

                # 执行事件
                if evt["type"] == "click":
                    pyautogui.click(x=evt["x"], y=evt["y"], button=evt["button"])
                elif evt["type"] == "move":
                    pyautogui.moveTo(evt["x"], evt["y"], duration=0)
                elif evt["type"] == "keypress":
                    try:
                        pyautogui.press(evt["key"])
                    except:
                        pass

            self.root.after(0, lambda l=loop: self.macro_status_label.config(
                text=f"播放中：{self.current_macro_name} (第{l}轮)", foreground="blue"))

        # 播放结束
        self.root.after(0, self._on_macro_finish)

    def _on_macro_finish(self):
        self.play_btn.config(state="normal")
        self.stop_play_btn.config(state="disabled")
        self.macro_status_label.config(text="播放完成", foreground="green")

    # ========== 原有功能 ==========

    def toggle_topmost(self):
        self.root.attributes("-topmost", self.topmost_var.get())
        self.save_config()

    def format_hotkey(self, hotkey_str):
        return hotkey_str.replace("<", "").replace(">", "").upper()

    def start_hotkey_listener(self):
        if self.listener:
            try:
                self.listener.stop()
            except:
                pass
        try:
            self.listener = keyboard.GlobalHotKeys({
                self.config["hotkey_start"]: self.start_clicking,
                self.config["hotkey_stop"]: self.stop_clicking,
                self.config["hotkey_capture"]: self.capture_position,
            })
            self.listener.start()
        except Exception as e:
            messagebox.showwarning("提示", f"快捷键注册失败: {e}\n可使用界面按钮操作")

    def open_hotkey_settings(self):
        win = tk.Toplevel(self.root)
        win.title("修改快捷键")
        win.geometry("320x240")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="点击输入框后按下你想要的按键", font=("微软雅黑", 10)).pack(pady=10)

        entries = {}

        def make_row(label, key_name, current):
            frame = ttk.Frame(win)
            frame.pack(fill="x", padx=20, pady=5)
            ttk.Label(frame, text=label, width=12).pack(side="left")
            var = tk.StringVar(value=self.format_hotkey(current))
            entry = ttk.Entry(frame, textvariable=var, width=15, justify="center")
            entry.pack(side="left")
            entries[key_name] = {"var": var, "entry": entry}

            def on_key_press(e):
                key = e.keysym.lower()
                mods = []
                if e.state & 0x0004: mods.append("ctrl")
                if e.state & 0x0001: mods.append("shift")
                if e.state & 0x0008: mods.append("alt")
                
                if key in ["control_l", "control_r", "shift_l", "shift_r", "alt_l", "alt_r"]:
                    return "break"
                
                if key.startswith("f") and key[1:].isdigit():
                    key_str = f"<{key}>"
                    display = key.upper()
                elif len(key) == 1:
                    display = "+".join([m.title() for m in mods] + [key.upper()])
                    if mods:
                        key_str = "+".join(mods + [key])
                    else:
                        key_str = f"<{key}>"
                else:
                    key_str = f"<{key}>"
                    display = key.title()
                
                var.set(display)
                entries[key_name]["new_raw"] = key_str
                return "break"

            entry.bind("<KeyPress>", on_key_press)

        make_row("开始连点:", "hotkey_start", self.config["hotkey_start"])
        make_row("停止连点:", "hotkey_stop", self.config["hotkey_stop"])
        make_row("取坐标:", "hotkey_capture", self.config["hotkey_capture"])

        def save_hotkeys():
            changed = False
            for key in ["hotkey_start", "hotkey_stop", "hotkey_capture"]:
                if "new_raw" in entries[key]:
                    self.config[key] = entries[key]["new_raw"]
                    changed = True
            if changed:
                self.save_config()
                self.start_hotkey_listener()
                self.start_btn.config(text="开始连点 (" + self.format_hotkey(self.config["hotkey_start"]) + ")")
                self.stop_btn.config(text="停止连点 (" + self.format_hotkey(self.config["hotkey_stop"]) + ")")
                messagebox.showinfo("成功", "快捷键已更新！", parent=win)
            win.destroy()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="保存", command=save_hotkeys, width=10).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="取消", command=win.destroy, width=10).pack(side="left", padx=10)

    def capture_position(self):
        x, y = pyautogui.position()
        self.pos_x_var.set(str(x))
        self.pos_y_var.set(str(y))
        self.use_pos_var.set(True)

    def start_clicking(self):
        if not self.stop_event.is_set():
            return
        try:
            self.interval = max(10, int(self.interval_var.get()))
            self.max_clicks = max(0, int(self.times_var.get()))
            if self.use_pos_var.get():
                self.target_x = int(self.pos_x_var.get())
                self.target_y = int(self.pos_y_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            return

        self.click_count = 0
        self.paused = False
        self.stop_event.clear()
        self.status_label.config(text="状态：连点运行中", foreground="green")
        self.pause_label.config(text="")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        self.click_thread = threading.Thread(target=self.click_loop, daemon=True)
        self.click_thread.start()

    def stop_clicking(self):
        self.stop_event.set()
        self.paused = False
        self.status_label.config(text="状态：已停止", foreground="red")
        self.pause_label.config(text="")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.save_config()

    def fast_click_at(self, x, y, button):
        screen_width = ctypes.windll.user32.GetSystemMetrics(0)
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)
        abs_x = int(x * 65535 / screen_width)
        abs_y = int(y * 65535 / screen_height)

        if button == "left":
            down, up = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
        else:
            down, up = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP

        ctypes.windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | down, abs_x, abs_y, 0, 0)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_ABSOLUTE | up, abs_x, abs_y, 0, 0)

    def click_loop(self):
        button = self.button_var.get()
        smart_pause = self.smart_pause_var.get()
        return_mouse = self.return_mouse_var.get()
        use_pos = self.use_pos_var.get()

        last_mouse_pos = pyautogui.position()
        last_move_time = time.time()  # 用真实时间戳，不受点击间隔影响

        while not self.stop_event.is_set():
            current_pos = pyautogui.position()

            if smart_pause and use_pos:
                moved = (abs(current_pos[0] - last_mouse_pos[0]) > 2 or 
                         abs(current_pos[1] - last_mouse_pos[1]) > 2)
                if moved:
                    last_move_time = time.time()  # 移动了，刷新时间戳
                    last_mouse_pos = current_pos
                    if not self.paused:
                        self.paused = True
                        self.root.after(0, lambda: self.pause_label.config(text="检测到鼠标操作，暂停中..."))
                else:
                    # 用真实时间差判断是否静止够500ms
                    if self.paused and (time.time() - last_move_time) >= 0.5:
                        self.paused = False
                        self.root.after(0, lambda: self.pause_label.config(text=""))

                if self.paused:
                    # 暂停状态下分片等待，随时响应停止
                    wait_ms = self.interval
                    while wait_ms > 0 and not self.stop_event.is_set():
                        chunk = min(wait_ms, 20)
                        time.sleep(chunk / 1000.0)
                        wait_ms -= chunk
                        # 等待过程中也要检测是否已经静止够了
                        if (time.time() - last_move_time) >= 0.5:
                            break
                    continue

            if self.max_clicks > 0 and self.click_count >= self.max_clicks:
                self.root.after(0, self.stop_clicking)
                break

            if use_pos and self.target_x is not None:
                original_pos = current_pos
                self.fast_click_at(self.target_x, self.target_y, button)
                if return_mouse:
                    pyautogui.moveTo(original_pos[0], original_pos[1], duration=0)
            else:
                pyautogui.click(button=button)

            self.click_count += 1
            self.root.after(0, lambda: self.count_label.config(
                text=f"已点击：{self.click_count} 次"))

            # 点击后等待
            wait_ms = self.interval
            while wait_ms > 0 and not self.stop_event.is_set():
                chunk = min(wait_ms, 20)
                time.sleep(chunk / 1000.0)
                wait_ms -= chunk

    def uninstall(self):
        result = messagebox.askyesno("卸载确认", 
            "即将彻底卸载鼠标连点器，将删除以下内容：\n\n"
            "• 配置文件 clicker_config.json（含所有宏）\n"
            "• 打包中间文件 build 文件夹\n"
            "• 打包配置文件 .spec\n"
            "• Python 缓存 __pycache__\n"
            "• 源代码文件 mouse_clicker.py\n\n"
            "注意：正在运行的exe主程序无法自删，卸载完成后请手动删除exe文件。\n\n"
            "确定卸载吗？")
        if not result:
            return

        deleted = []
        failed = []

        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            exe_name = os.path.basename(sys.executable)
        else:
            exe_dir = os.path.dirname(os.path.abspath(__file__))
            exe_name = "mouse_clicker.py"

        targets_same_dir = [
            "clicker_config.json",
            "__pycache__",
            "mouse_clicker.py",
        ]

        targets_parent_dir = [
            "build",
            "dist",
            "__pycache__",
            "mouse_clicker.py",
        ]

        for name in targets_same_dir:
            path = os.path.join(exe_dir, name)
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    deleted.append(name)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                    deleted.append(name + " 文件夹")
            except Exception as e:
                if os.path.exists(path):
                    failed.append(f"{name} ({e})")

        try:
            for f in os.listdir(exe_dir):
                if f.endswith(".spec"):
                    os.remove(os.path.join(exe_dir, f))
                    deleted.append(f)
        except:
            pass

        parent_dir = os.path.dirname(exe_dir)
        for name in targets_parent_dir:
            path = os.path.join(parent_dir, name)
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    deleted.append("上级目录/" + name)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                    deleted.append("上级目录/" + name + " 文件夹")
            except Exception as e:
                if os.path.exists(path):
                    failed.append(f"上级目录/{name} ({e})")

        try:
            for f in os.listdir(parent_dir):
                if f.endswith(".spec"):
                    os.remove(os.path.join(parent_dir, f))
                    deleted.append("上级目录/" + f)
        except:
            pass

        msg = "卸载完成！\n\n"
        if deleted:
            msg += "已清理：\n"
            for d in deleted:
                msg += f"  ✓ {d}\n"
            msg += "\n"
        
        if failed:
            msg += "以下未能删除（可能被占用）：\n"
            for f in failed:
                msg += f"  ✗ {f}\n"
            msg += "\n"

        msg += f"最后一步：手动删除「{exe_name}」主程序文件，就彻底干净了。"

        messagebox.showinfo("卸载完成", msg)
        self.on_close()

    def on_close(self):
        self.save_config()
        self.stop_event.set()
        self.macro_stop_event.set()
        if self.listener:
            try:
                self.listener.stop()
            except:
                pass
        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except:
                pass
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except:
                pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MouseClicker(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()