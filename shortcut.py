import os.path
import time
import tkinter as tk
from pathlib import Path
import win32clipboard
from win32api import GetCursorPos
from screeninfo import get_monitors
from PIL import Image, ImageTk, ImageGrab, ImageOps, ImageEnhance
from toolbar import Toolbar
from io import BytesIO
from tkinter import filedialog
from listenqueue import start_queue
from gifwin import GifRecorder

class Shortcut(tk.Toplevel):
    def __init__(self, master,scale=None,settings=None):
        super().__init__(master)
        self.scale = scale
        self.settings = settings
        self._init_status()
        self._init_ui()
        self._init_bind()
        self.setup_git_info()

    def _init_status(self):
        self.OUTPUT_PATH = Path(__file__).parent
        self.ASSETS_PATH = self.OUTPUT_PATH / Path('media')
        self.queue = start_queue(max=1)
        self.shortcuting = False
        self.marking = False
        self.markid = 1
        self.mark_stack = []
        self.startx = 0
        self.starty = 0
        self.shortcut_area = [(0,0),(0,0)]
        self.isopened = True
        self.glass_color = '#BBB5C2'
        self.access_check_image = self.access_gif_image = self.access_re_image = self.access_rect_image = self.access_save_image = None

    def _init_ui(self):
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        cs, cy = GetCursorPos()
        self.myscreen = self.get_monitor_screen(cs, cy)
        ws = self.myscreen.width
        hs = self.myscreen.height
        x = self.myscreen.x
        y = self.myscreen.y
        self.geometry(f'{ws}x{hs}+{x}+{y}')

        self.canvas = tk.Canvas(self, height=hs, width=ws, highlightthickness=0, cursor='plus')
        self.canvas.pack(padx=0, pady=0)
        self.get_current_screen()
        self.tool_bar = Toolbar(self, self.scale)
        self.config_toolbar_command()
        self.tool_bar.place_forget()

    def get_monitor_screen(self, x, y):
        monitors = get_monitors()
        for m in reversed(monitors):
            if m.x <= x <= m.width + m.x and m.y <= y <= m.height + m.y:
                return m
        return monitors[0]

    def get_current_screen(self):
        self.current_screen_image = ImageGrab.grab(bbox=(
        self.myscreen.x, self.myscreen.y, self.myscreen.x + self.myscreen.width,
        self.myscreen.y + self.myscreen.height), all_screens=True)
        self.current_screen_image = ImageEnhance.Brightness(self.current_screen_image).enhance(0.75)
        self.cv_img = ImageTk.PhotoImage(self.current_screen_image)
        self.canvas.create_image(0, 0, image=self.cv_img, anchor=tk.NW)

    def config_toolbar_command(self):
        self.tool_bar.confirm_btn.configure(command=lambda :self.send_shortcut(self.shortcut_area[0],self.shortcut_area[1]))
        self.tool_bar.save_btn.configure(command=lambda :self.save_shortcut(self.shortcut_area[0],self.shortcut_area[1]))
        self.tool_bar.gif_btn.configure(command=self.start_gif)
        self.tool_bar.mark_btn.configure(command=self.mark_mode)
        self.tool_bar.undo_btn.configure(command=self.undo_mark)

    def send_shortcut(self, leftup=None, rightdown=None):
        def send_to_clipboard(clip_type, data):
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(clip_type, data)
            win32clipboard.CloseClipboard()
        output = BytesIO()
        image = ImageGrab.grab(bbox= leftup+rightdown, all_screens=True)
        image = ImageEnhance.Brightness(image).enhance(1.33)
        image.convert('RGB').save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()
        send_to_clipboard(win32clipboard.CF_DIB, data)
        self.isopened = False
        self.destroy()

    def center_filedialog(self):
        self.center_w = tk.Tk()
        x = self.center_w.winfo_screenwidth() // 4
        y = self.center_w.winfo_screenheight() // 4
        self.center_w.geometry(f'10x10+{x}+{y}')
        self.center_w.overrideredirect(True)
        self.center_w.attributes('-transparentcolor', self.glass_color)
        self.center_w.configure(bg=self.glass_color)

    def save_shortcut(self, leftup=None, rightdown=None):
        image = ImageGrab.grab(bbox=leftup+rightdown, all_screens=True)
        image = ImageEnhance.Brightness(image).enhance(1.33)
        self.close_window(0)
        self.center_filedialog()
        ask = filedialog.asksaveasfilename(parent=self.center_w, initialdir=self.settings.recent_path, defaultextension='.png',
                                           filetypes=[("PNG Files", "*.png"), ("JPG Files", "*.jpg")])
        self.center_w.destroy()
        if ask:
            self.settings.update('recent_path', os.path.dirname(ask))
            image.save(ask)

    def close_window(self, event, second=0.0):
        time.sleep(second)
        self.isopened = False
        self.destroy()

    def start_gif(self):
        if self.queue.full():
            pass
        else:
            self.queue.put(self.make_countdown_area)
            self.tool_bar.disable_btns()
            self.lock_bind()

    def make_countdown_area(self):
        if self.shortcut_area:
            x0 = self.shortcut_area[0][0] - self.myscreen.x
            y0 = self.shortcut_area[0][1] - self.myscreen.y
            x1 = self.shortcut_area[1][0] - self.myscreen.x
            y1 = self.shortcut_area[1][1] - self.myscreen.y
            x = x0 + (x1 - x0) // 2
            y = y0 + (y1 - y0) // 2
            self.countdown_img = ImageTk.PhotoImage(self.current_screen_image.crop((x, y, x + 40, y + 40)))
            self.countdown_label.place(x=x,y=y,width=40,height=40)
            self.countdown_label.config(image=self.countdown_img,compound=tk.CENTER)
            self.countdown()

    def countdown(self):
        self.countdown_times.set('3')
        while int(self.countdown_times.get()) > 1:
            time.sleep(1)
            now = int(self.countdown_times.get())
            cd = str(now -1)
            self.countdown_times.set(cd)
        time.sleep(1)
        try:
            self.countdown_label.place_forget()
            self.update()
            self.withdraw()
            self.event_generate('<<gif_recorder>>')
        except Exception:
            pass

    def lock_bind(self, with_cancel=True):
        self.canvas.unbind('<Button-1>')
        self.canvas.unbind('<Motion>')
        self.canvas.unbind('<ButtonRelease-1>')
        if with_cancel:
            self.canvas.unbind('<Button-3>')

    def unlock_bind(self):
        self.canvas.bind('<Button-1>', self.record_start)
        self.canvas.bind('<Motion>', self.update_paint)
        self.canvas.bind('<ButtonRelease-1>', self.paint_release)
        self.canvas.bind('<Button-3>', lambda e:self.close_window(e,second=0.1))

    def mark_mode(self):
        # self.canvas.winfo_geometry()
        self.tool_bar.mark_btn.configure(bg=self.tool_bar.act_color,relief=tk.SUNKEN)
        self.configure(cursor='tcross')
        self.change_bind()

    def change_bind(self):
        self.canvas.tag_bind('shortcut_area', '<Button-1>', self.record_mark_start)
        self.canvas.tag_bind('shortcut_area', '<Motion>', self.update_mark_paint)
        self.canvas.tag_bind('shortcut_area', '<ButtonRelease-1>', self.mark_paint_release)
        self.lock_bind(with_cancel=False)

    def record_mark_start(self, event):
        self.marking = True
        self.startx = event.x
        self.starty = event.y

    def update_mark_paint(self, event):
        if self.marking:
            self.canvas.delete(f'mark{self.markid}')
            leftx, lefty = min(self.startx, event.x), min(self.starty, event.y)
            rightx, righty = max(self.startx, event.x), max(self.starty, event.y)
            self.canvas.create_rectangle(leftx, lefty, rightx, righty, outline='red', width=1, tags=f'mark{self.markid}')

    def mark_paint_release(self, event):
        self.marking = False
        self.mark_stack.append(f'mark{self.markid}')
        self.markid += 1

    def undo_mark(self):
        if len(self.mark_stack) > 0:
            pre_del = self.mark_stack.pop()
            self.canvas.delete(pre_del)
        else:
            self._init_bind()
            self.canvas.tag_unbind('shortcut_area', '<Button-1>')
            self.canvas.tag_unbind('shortcut_area', '<Motion>')
            self.canvas.tag_unbind('shortcut_area', '<ButtonRelease-1>')
            self.tool_bar.mark_btn.configure(bg=self.tool_bar.bg_color,relief=tk.FLAT)
            self.configure(cursor='arrow')

    def _init_bind(self):
        self.canvas.bind('<Button-1>', self.record_start)
        self.canvas.bind('<Motion>', self.update_paint)
        self.canvas.bind('<ButtonRelease-1>', self.paint_release)
        self.canvas.bind('<Button-3>', lambda e:self.close_window(e,second=0.1))
        self.bind('<<gif_recorder>>', self.open_gif_recorder)

    def record_start(self, event):
        self.shortcuting = True
        self.startx = event.x
        self.starty = event.y
        # 清空前一次记录
        self.shortcut_area = None

    def update_paint(self, event):
        if self.shortcuting:
            self.canvas.delete('shortcut_area')
            leftx, lefty = min(self.startx, event.x), min(self.starty, event.y)
            rightx, righty = max(self.startx, event.x), max(self.starty, event.y)
            self.shortcut_area = [(leftx, lefty),(rightx, righty)]
            image = Image.new('RGBA',(rightx - leftx, righty - lefty), (255, 255, 255, 0))
            self.rec_image = ImageTk.PhotoImage(ImageOps.expand(image, border=1, fill='#0378C1'))
            self.canvas.create_image(leftx-1, lefty-1, image=self.rec_image, anchor=tk.NW, tags='shortcut_area')

    def paint_release(self, event):
        self.shortcuting = False
        if self.shortcut_area:
            # 放置一次获取组件宽度
            self.tool_bar.place(x=event.x, y=event.y)
            self.tool_bar.update()
            offsetx = self.tool_bar.winfo_width() - self.tool_bar.adapt_size(5)
            offsety = self.tool_bar.adapt_size(15)
            self.tool_bar.place(x=event.x - offsetx, y=event.y + offsety)
            x0 = self.shortcut_area[0][0] + self.myscreen.x
            y0 = self.shortcut_area[0][1] + self.myscreen.y
            x1 = self.shortcut_area[1][0] + self.myscreen.x
            y1 = self.shortcut_area[1][1] + self.myscreen.y
            self.shortcut_area = [(x0,y0),(x1,y1)]
            self.settings.update('recent_area', self.shortcut_area)

    def open_gif_recorder(self, event):
        self.gif_recorder = GifRecorder(self, self.shortcut_area[0] + self.shortcut_area[1], settings=self.settings,
                                        screen=self.myscreen)
        self.update()

    def setup_git_info(self):
        self.countdown_times = tk.StringVar()
        self.countdown_label = tk.Label(self, textvariable=self.countdown_times, font=('Arial', 15), foreground='red')

    def relative_to_assets(self, path: str) -> Path:
        return self.ASSETS_PATH / Path(path)