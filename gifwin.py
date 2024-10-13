import os.path
import threading
import tkinter as tk
from pathlib import Path
from PIL import Image, ImageTk, ImageGrab
import time
from tkinter import filedialog
from win32api import GetCursorPos

class GifRecorder(tk.Toplevel):
    def __init__(self, master, area=None, settings=None, screen:object=None):
        super().__init__(master)
        self.settings = settings
        self.screen = screen
        self.scale = self.screen.width / 3120
        self.recording = True
        self.OUTPUT_PATH = Path(__file__).parent
        self.ASSETS_PATH = self.OUTPUT_PATH / Path('media')
        self._init_ui()
        self.setup_hint_area(area)
        self.setup_tool_bar()
        self.start(area)

    def adapt_size(self, value):
        if value:
            return int(value * self.scale)
        else:
            return None

    def _init_ui(self):
        self.overrideredirect(True)
        ws = self.screen.width
        hs = self.screen.height
        x = self.screen.x
        y = self.screen.y
        self.geometry(f'{ws}x{hs}+{x}+{y}')
        self.glass_color = '#BBB5C2'
        self.config(bg=self.glass_color)
        self.canvas = tk.Canvas(self, height=hs, width=ws, highlightthickness=0, bg=self.glass_color)
        self.canvas.pack(padx=0, pady=0)
        self.attributes('-transparentcolor', self.glass_color)
        self.attributes('-topmost', True)
        self.pointer = Image.open(self.relative_to_assets('pointer.png'))
        _, _, _, self.alpha = self.pointer.split()

    def setup_hint_area(self, area):
        a, b, c, d = area
        a = a - self.screen.x - 1
        b = b - self.screen.y - 1
        c = c - self.screen.x + 1
        d = d - self.screen.y + 1
        self.canvas.create_rectangle(a, b, c, d, outline='red', dash=(1,1), width=2)

    def setup_tool_bar(self):
        x = (self.screen.width - self.adapt_size(92)) / 2
        self.record_img = ImageTk.PhotoImage(
            Image.open(self.relative_to_assets('record.png')).resize((self.adapt_size(92), self.adapt_size(40))))
        self.stop_img = ImageTk.PhotoImage(
            Image.open(self.relative_to_assets('stop.png')).resize((self.adapt_size(40), self.adapt_size(40))))
        self.canvas.create_image(x, 0, image=self.record_img, anchor=tk.NW)
        self.stop_btn = tk.Button(self, image=self.stop_img, relief=tk.FLAT, command=self.close_window)
        self.stop_btn.place(x=x + self.adapt_size(92), y=0, width=self.adapt_size(40), height=self.adapt_size(40))

    def close_window(self):
        self.recording = False
        self.master.isopened = False
        self.master.destroy()

    def start(self, area):
        threading.Thread(target=self.record_gif, daemon=True, args=(area, )).start()

    def center_filedialog(self):
        self.center_w = tk.Tk()
        x = self.center_w.winfo_screenwidth() // 4
        y = self.center_w.winfo_screenheight() // 4
        self.center_w.geometry(f'10x10+{x}+{y}')
        self.center_w.overrideredirect(True)
        self.center_w.attributes('-transparentcolor', self.glass_color)
        self.center_w.configure(bg=self.glass_color)

    def record_gif(self, area):
        def to_gif(img_list, start, end):
            im = img_list[0]
            self.center_filedialog()
            ask = filedialog.asksaveasfilename(parent=self.center_w, initialdir=self.settings.recent_path,
                                               defaultextension='.gif', filetypes=[("GIF Files", "*.gif")])
            self.center_w.destroy()
            if ask:
                self.settings.update('recent_path', os.path.dirname(ask))
                sec = (end - start)
                dur = sec / (len(img_list) - 1) * 1000
                im.save(ask, save_all=True, append_images=img_list[1:], loop=0, duration=dur)
        img_list = []
        start = time.time()
        while self.recording:
            img = self.capture(area, self.settings.pointer_show)
            img_list.append(img)
        end = time.time()
        if img_list:
            to_gif(img_list, start, end)

    def capture(self, area, pointer=False):
        img = ImageGrab.grab(area, all_screens=True)
        if pointer:
            mx, my = GetCursorPos()
            mouse_position = (mx - area[0], my - area[1])
            img.paste(self.pointer, mouse_position, mask=self.alpha)
        return img

    def relative_to_assets(self, path: str) -> Path:
        return self.ASSETS_PATH / Path(path)