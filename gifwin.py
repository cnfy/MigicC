import os.path
import threading
import tkinter as tk
from pathlib import Path
from PIL import Image, ImageTk, ImageGrab
import time
from queue import Queue
from tkinter import messagebox
from tkinter import filedialog
from win32api import GetCursorPos

class GifRecorder(tk.Toplevel):
    def __init__(self, master, area=None, settings=None, screen:object=None):
        super().__init__(master)
        self.settings = settings
        self.screen = screen
        self.area = area
        self.scale = min(self.screen.width / 3120, self.screen.height / 2080)
        self.recording = True
        self.result_queue = Queue()
        self.frames = []
        self.OUTPUT_PATH = Path(__file__).parent
        self.ASSETS_PATH = self.OUTPUT_PATH / Path('media')
        self._init_ui()
        self.setup_hint_area(area)
        self.setup_tool_bar()
        self.start(area)
        self.after(50, self.poll_result)

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
        # Prefer a position outside the selected region, so controls do not enter frames.
        y = 0
        a, b, c, d = self.area
        local_top, local_bottom = b-self.screen.y, d-self.screen.y
        control_height = self.adapt_size(40)
        if local_top < control_height:
            if self.screen.height-local_bottom >= control_height:
                y = self.screen.height-control_height
            elif a-self.screen.x >= self.adapt_size(132):
                x = 0
            elif self.screen.width-(c-self.screen.x) >= self.adapt_size(132):
                x = self.screen.width-self.adapt_size(132)
        self.record_img = ImageTk.PhotoImage(
            Image.open(self.relative_to_assets('record.png')).resize((self.adapt_size(92), self.adapt_size(40))))
        self.stop_img = ImageTk.PhotoImage(
            Image.open(self.relative_to_assets('stop.png')).resize((self.adapt_size(40), self.adapt_size(40))))
        self.canvas.create_image(x, y, image=self.record_img, anchor=tk.NW)
        self.stop_btn = tk.Button(self, image=self.stop_img, relief=tk.FLAT, command=self.close_window)
        self.stop_btn.place(x=x + self.adapt_size(92), y=y, width=self.adapt_size(40), height=self.adapt_size(40))

    def close_window(self):
        self.recording = False
        self.withdraw()
        self.stop_btn.configure(state='disabled')

    def start(self, area):
        threading.Thread(target=self.record_gif, daemon=True, args=(area, )).start()

    def poll_result(self):
        if self.result_queue.empty():
            self.after(50, self.poll_result)
            return
        result = self.result_queue.get()
        self.withdraw()
        if isinstance(result, Exception):
            messagebox.showerror('Recording failed', str(result), parent=self.master.master)
            self.master.isopened = False
            self.master.destroy()
            return
        frames, durations = result
        ask = filedialog.asksaveasfilename(parent=self.master.master,
                initialdir=self.settings.recent_path, defaultextension='.gif',
                filetypes=[('GIF Files', '*.gif')])
        if ask and frames:
            # Encoding stays off the UI thread; completion is polled on Tk.
            def save():
                try:
                    frames[0].save(ask, save_all=True, append_images=frames[1:],
                                   loop=0, duration=durations, optimize=False)
                    self.result_queue.put(('saved', ask))
                except Exception as error:
                    self.result_queue.put(error)
            threading.Thread(target=save, daemon=True).start()
            self.after(50, self.poll_save)
        else:
            self.master.isopened = False
            self.master.destroy()

    def poll_save(self):
        if self.result_queue.empty():
            self.after(50, self.poll_save)
            return
        result = self.result_queue.get()
        if isinstance(result, Exception):
            messagebox.showerror('Save failed', str(result), parent=self.master.master)
        else:
            self.settings.update('recent_path', os.path.dirname(result[1]))
        self.master.isopened = False
        self.master.destroy()

    def record_gif(self, area):
        frames, timestamps = [], []
        start = time.monotonic()
        interval = 1 / self.settings.gif_fps
        # Palette frames need about one byte per pixel. Cap retained pixels at 128 MiB.
        pixels = max(1, (area[2]-area[0]) * (area[3]-area[1]))
        limit = max(1, min(self.settings.gif_fps*self.settings.gif_max_seconds,
                           128*1024*1024 // pixels))
        pointer = self.settings.pointer_show
        try:
            while self.recording and len(frames) < limit and time.monotonic()-start < self.settings.gif_max_seconds:
                tick = time.monotonic()
                img = self.capture(area, pointer).convert('RGB')
                frames.append(img.quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                                           dither=Image.Dither.FLOYDSTEINBERG))
                timestamps.append(tick)
                time.sleep(max(0, interval-(time.monotonic()-tick)))
            end = time.monotonic()
            durations = [max(10, round((b-a)*1000)) for a,b in
                         zip(timestamps, timestamps[1:]+[end])]
            self.recording = False
            self.result_queue.put((frames, durations))
        except Exception as error:
            self.recording = False
            self.result_queue.put(error)

    def capture(self, area, pointer=False):
        img = ImageGrab.grab(area, all_screens=True)
        if pointer:
            mx, my = GetCursorPos()
            mouse_position = (mx - area[0], my - area[1])
            img.paste(self.pointer, mouse_position, mask=self.alpha)
        return img

    def relative_to_assets(self, path: str) -> Path:
        return self.ASSETS_PATH / Path(path)
