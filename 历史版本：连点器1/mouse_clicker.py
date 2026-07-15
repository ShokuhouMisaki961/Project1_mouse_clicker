import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import sys
import shutil
import pyautogui
from pynput import keyboard
import json
import ctypes

pyautogui.PAUSE = 0

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
    "win_width": 440,
    "win_height": 640
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
        self.root.title("鼠标连点器")

        # ✅ 先加载配置（修复初始化顺序）
        self.config = self.load_config()

        # 再用配置设置窗口尺寸
        w = int(self.config.get("win_width", 440))
        h = int(self.config.get("win_height", 640))
        self.root.geometry(f"{w}x{h}")
        self.root.minsize(400, 580)
        self.root.resizable(True, True)

        self.stop_event = threading.Event()
        self.stop_event.set()
        self.click_thread = None
        self.click_count = 0
        self.target_x = None
        self.target_y = None
        self.listener = None
        self.paused = False

        self.root.attributes("-topmost", self.config["topmost"])
        self.build_ui()
        self.start_hotkey_listener()

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
        return DEFAULT_CONFIG.copy()

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
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        title_label = ttk.Label(main_frame, text="鼠标连点器", font=("微软雅黑", 16, "bold"))
        title_label.pack(pady=8)

        # === 基础设置 ===
        setting_frame = ttk.LabelFrame(main_frame, text="基础设置", padding=10)
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

        # === 窗口设置 ===
        win_frame = ttk.LabelFrame(main_frame, text="窗口设置", padding=10)
        win_frame.pack(fill="x", pady=5)

        self.topmost_var = tk.BooleanVar(value=self.config["topmost"])
        ttk.Checkbutton(win_frame, text="窗口置顶（切换游戏/软件时仍可见）", 
                        variable=self.topmost_var, 
                        command=self.toggle_topmost).pack(anchor="w", pady=2)

        ttk.Label(win_frame, text="💡 拖动窗口边缘可自由缩放大小，右上角可最大化", 
                  foreground="gray", font=("微软雅黑", 9)).pack(anchor="w", pady=2)

        # === 固定坐标 ===
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
        ttk.Checkbutton(pos_frame, text="点击后鼠标归位（不点这个鼠标就留在目标位置）", 
                        variable=self.return_mouse_var).pack(anchor="w", pady=2)

        self.smart_pause_var = tk.BooleanVar(value=self.config["smart_pause"])
        ttk.Checkbutton(pos_frame, text="✨ 智能防打扰（你移动鼠标时自动暂停连点）", 
                        variable=self.smart_pause_var).pack(anchor="w", pady=2)

        # === 状态区 ===
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

        # === 主按钮 ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=5)
        self.start_btn = ttk.Button(btn_frame, text="开始 (" + self.format_hotkey(self.config["hotkey_start"]) + ")", 
                                    command=self.start_clicking, width=14)
        self.start_btn.grid(row=0, column=0, padx=6)
        self.stop_btn = ttk.Button(btn_frame, text="停止 (" + self.format_hotkey(self.config["hotkey_stop"]) + ")", 
                                   command=self.stop_clicking, width=14, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=6)

        # === 底部功能按钮 ===
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(pady=5)
        ttk.Button(bottom_frame, text="⚙ 修改快捷键", command=self.open_hotkey_settings, width=14).grid(row=0, column=0, padx=5)
        ttk.Button(bottom_frame, text="🗑 一键卸载", command=self.uninstall, width=14).grid(row=0, column=1, padx=5)

        # 底部提示
        tip_label = ttk.Label(main_frame, 
            text="智能防打扰：手动移动鼠标自动暂停，静止0.5秒后自动恢复\n完美解决「连点时没法用鼠标」的问题",
            foreground="gray", font=("微软雅黑", 9), justify="center")
        tip_label.pack(pady=8, side="bottom")

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
                self.start_btn.config(text="开始 (" + self.format_hotkey(self.config["hotkey_start"]) + ")")
                self.stop_btn.config(text="停止 (" + self.format_hotkey(self.config["hotkey_stop"]) + ")")
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
        self.status_label.config(text="状态：运行中", foreground="green")
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
        idle_time = 0

        while not self.stop_event.is_set():
            current_pos = pyautogui.position()

            if smart_pause and use_pos:
                moved = (abs(current_pos[0] - last_mouse_pos[0]) > 2 or 
                         abs(current_pos[1] - last_mouse_pos[1]) > 2)
                if moved:
                    idle_time = 0
                    if not self.paused:
                        self.paused = True
                        self.root.after(0, lambda: self.pause_label.config(text="检测到鼠标操作，暂停中..."))
                else:
                    idle_time += 10
                    if self.paused and idle_time >= 500:
                        self.paused = False
                        self.root.after(0, lambda: self.pause_label.config(text=""))

                last_mouse_pos = current_pos

                if self.paused:
                    wait_ms = self.interval
                    while wait_ms > 0 and not self.stop_event.is_set():
                        chunk = min(wait_ms, 10)
                        time.sleep(chunk / 1000.0)
                        wait_ms -= chunk
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

            wait_ms = self.interval
            while wait_ms > 0 and not self.stop_event.is_set():
                chunk = min(wait_ms, 10)
                time.sleep(chunk / 1000.0)
                wait_ms -= chunk

    def uninstall(self):
        result = messagebox.askyesno("卸载确认", 
            "即将彻底卸载鼠标连点器，将删除以下内容：\n\n"
            "• 配置文件 clicker_config.json\n"
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
        if self.listener:
            try:
                self.listener.stop()
            except:
                pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MouseClicker(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()