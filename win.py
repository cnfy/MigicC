import time
import tkinter as tk
from pathlib import Path
from win32api import GetMonitorInfo, MonitorFromPoint, GetCursorPos
from PIL import Image, ImageTk
import threading
from dstk import DsButton


class ToolPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.OUTPUT_PATH = Path(__file__).parent
        self.ASSETS_PATH = self.OUTPUT_PATH / Path('media')
        self._init_info()
        self.loading_image()
        self._init_ui()
        self.setup_windows()
        self.motion_bind()

    def _init_info(self):
        self.bts = {}
        self.menus = {}
        self.button_imgs = {}
        self.abs_y = 300
        self.canvas_options_show = False
        self.canvas_settings_show = False
        self.magic_mode = 0 # 0 is copy. 1 is save
        self.scale = self.winfo_screenwidth() / 3120
        self.select_sc = tk.StringVar()
        self.magic_sc = tk.StringVar()
        self.slb_var = tk.IntVar()
        self.slb_var.set(1)
        self.mlb_var = tk.IntVar()
        self.mlb_var.set(1)

    def adapt_size(self, value):
        if value:
            return int(value * self.scale)
        else:
            return None

    def loading_image(self):
        self.panimg = Image.open(self.relative_to_assets('panel.png')).resize(
            (self.adapt_size(502), self.adapt_size(62)))
        self.panimg_tk = ImageTk.PhotoImage(self.panimg)
        self.opt_img = Image.open(self.relative_to_assets('exit_bg.png')).resize(
            (self.adapt_size(102), self.adapt_size(42)))
        self.opt_img_tk = ImageTk.PhotoImage(self.opt_img)
        self.exit_btn_img = Image.open(self.relative_to_assets('exit_btn.png')).resize(
            (self.adapt_size(80), self.adapt_size(42)))
        self.exit_btn_img_tk = ImageTk.PhotoImage(self.exit_btn_img)
        self.position_img = Image.open(self.relative_to_assets('position.png')).resize(
            (self.adapt_size(160), self.adapt_size(62)))
        self.position_img_tk = ImageTk.PhotoImage(self.position_img)
        self.set_img = Image.open(self.relative_to_assets('settings.png')).resize(
            (self.adapt_size(352), self.adapt_size(202)))
        self.set_img_tk = ImageTk.PhotoImage(self.set_img)
        self.frame_img = Image.open(self.relative_to_assets('frame.png')).resize(
            (self.adapt_size(330), self.adapt_size(180)))
        self.frame_img_tk = ImageTk.PhotoImage(self.frame_img)
        self.lock_img = Image.open(self.relative_to_assets('lock.png')).resize(
            (self.adapt_size(20), self.adapt_size(20)))
        self.lock_img_tk = ImageTk.PhotoImage(self.lock_img)
        self.unlock_img = Image.open(self.relative_to_assets('unlock.png')).resize(
            (self.adapt_size(20), self.adapt_size(21)))
        self.unlock_img_tk = ImageTk.PhotoImage(self.unlock_img)
        self.button_light_img = ImageTk.PhotoImage(Image.open(self.relative_to_assets('button_light.png')).resize((self.adapt_size(60),self.adapt_size(60))))

    def _init_ui(self):
        self.glass_color = '#BBB5C2'
        self.config(bg=self.glass_color)

        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        self.width = self.adapt_size(502)
        self.height = self.adapt_size(self.abs_y * 2 + 60)
        monitor_info = GetMonitorInfo(MonitorFromPoint((0, 0)))
        monitor_area = monitor_info.get("Monitor")
        work_area = monitor_info.get("Work")
        self.taskbar_height = monitor_area[3] - work_area[3]
        self.x_position = ws - self.width - 10
        self.y_position = hs - self.height - self.taskbar_height + self.adapt_size(self.abs_y)
        self.geometry(f'{self.width}x{self.height}+{self.x_position}+{self.y_position}')
        self.attributes('-transparentcolor', self.glass_color)
        self.attributes('-topmost', True)
        self.overrideredirect(True)
        self.update()

    def setup_windows(self):
        self.setup_main_window()
        self.setup_option_window()
        self.setup_setting_window()

    def setup_main_window(self):
        self.canvas = tk.Canvas(self, bg=self.glass_color, bd=0, highlightthickness=0, relief=tk.FLAT)
        y = self.adapt_size(self.abs_y)
        self.canvas.place(x=0, y=y, relwidth=1, relheight=1)
        self.canvas.create_image(0, 0, image=self.panimg_tk, anchor=tk.NW)
        self.setup_main_menu()

    def setup_main_menu(self):
        self.add_menu(1, 18, self.abs_y, 60, 60, bg=self.panimg, icon='button_1.png')
        self.add_menu(2, 87, self.abs_y, 60, 60, bg=self.panimg, icon='button_2.png')
        self.light_label = tk.Label(self, image=self.button_light_img)
        self.add_position_display(bg=self.panimg)
        self.add_split_line()
        self.add_menu(3, 362, self.abs_y, 60, 60, self.show_settings, bg=self.panimg, icon='button_3.png')
        self.add_menu(4, 423, self.abs_y, 60, 60, self.show_options, bg=self.panimg, icon='button_4.png')

    def add_menu(self, id, place_x, place_y, width, height, func=None, bg=None, icon=None, icon_side=None):
        self.bts[id] = self.adapt_size(place_x)
        btn_back, btn_color = self.adaptbutton(id, bg=bg, width=width, height=height, icon=icon, icon_side=icon_side)
        self.button_imgs[id] = btn_back
        button = tk.Button(image=btn_back, borderwidth=0, bg=btn_color, activebackground=btn_color,
                           highlightthickness=0, command=func, relief=tk.FLAT, cursor='hand2')
        if place_y:
            button.place(x=self.adapt_size(place_x), y=self.adapt_size(place_y), width=self.adapt_size(width),
                         height=self.adapt_size(height))
        self.menus[id] = button

    def remove_menu(self, id):
        self.bts.pop(id)
        menu = self.menus.pop(id)
        menu.destroy()

    def adaptbutton(self, id=None, width=None, height=None, location=None, bg=None, icon=None, icon_side=None):
        def calculate_center(img1_size, img2_size):
            x = int(img1_size[0] / 2 - img2_size[0] / 2)
            y = int(img1_size[1] / 2 - img2_size[1] / 2)
            return (x, y)

        width = self.adapt_size(width)
        height = self.adapt_size(height)
        location = self.adapt_size(location)
        newimg = Image.new('RGBA', (width, height))
        if icon:
            if id:
                button_image = Image.open(self.relative_to_assets(icon)).convert('RGBA').resize((width, height))
                if not icon_side:
                    newimg.paste(button_image, calculate_center(newimg.size, button_image.size))
                elif icon_side == 'left':
                    newimg.paste(button_image, (0, calculate_center(newimg.size, button_image.size)[1]))
                btn_bak = bg.crop((self.bts.get(id), 0, self.bts.get(id) + width, height)).convert('RGBA')
            if location:
                btn_bak = bg.crop((location, 0, location + width, height)).convert('RGBA').resize((width, height))
            final = Image.new('RGBA', newimg.size)
            final = Image.alpha_composite(final, btn_bak)
            final = Image.alpha_composite(final, newimg)
            final = final.convert('RGB')
        else:
            final = bg.convert('RGB')
        btn_bak = ImageTk.PhotoImage(final)
        btn_color = final.resize((1, 1)).getpixel((0, 0))
        btn_color = '#%02x%02x%02x' % btn_color
        return btn_bak, btn_color

    def add_position_display(self, bg=None):
        self.position_display_var = tk.Variable()
        self.position_display_var.set(',')
        self.position_display = tk.Label(self, image=self.position_img_tk, textvariable=self.position_display_var,
                                         compound=tk.CENTER)
        self.position_display.place(x=self.adapt_size(155), y=self.adapt_size(self.abs_y), width=self.adapt_size(160),
                                    height=self.adapt_size(62))

    def add_split_line(self):
        self.canvas.create_rectangle(self.adapt_size(332), self.adapt_size(9), self.adapt_size(333),
                                     self.adapt_size(50), fill='#000000', outline='')

    def show_options(self):
        if self.canvas_options_show:
            self.canvas_options.place_forget()
            self.canvas_options_show = False
        else:
            if self.winfo_rooty() + self.adapt_size(self.abs_y - 54) > 0:
                y = self.adapt_size(self.abs_y - 54)
            else:
                y = self.adapt_size(self.abs_y + 74)
            self.canvas_options.place(x=self.adapt_size(400), y=y)
            self.canvas_options_show = True
            self.canvas_settings.place_forget()
            self.canvas_settings_show = False

    def setup_option_window(self):
        self.canvas_options = tk.Canvas(self, bg=self.glass_color, height=self.adapt_size(42),
                                        width=self.adapt_size(102), bd=0, highlightthickness=0)
        self.canvas_options.place(x=self.adapt_size(400), y=self.adapt_size(self.abs_y - 54))
        self.canvas_options.create_image(0, 0, image=self.opt_img_tk, anchor=tk.NW)
        self.canvas_options.place_forget()
        self.setup_option_menu()

    def setup_option_menu(self):
        self.bts[5] = self.adapt_size(0)
        button = tk.Button(self, image=self.exit_btn_img_tk, borderwidth=0, activebackground='#9778E9',
                           highlightthickness=0, relief=tk.FLAT, cursor='hand2')
        self.menus[5] = button
        self.canvas_options.create_window(self.adapt_size(10), 0, width=self.adapt_size(80), height=self.adapt_size(42),
                                          window=self.menus[5], anchor=tk.NW)

    def show_settings(self):
        if self.canvas_settings_show:
            self.canvas_settings.place_forget()
            self.canvas_settings_show = False
        else:
            if self.winfo_rooty() + self.adapt_size(self.abs_y - 214) > 0:
                y = self.adapt_size(self.abs_y - 214)
            else:
                y = self.adapt_size(self.abs_y + 74)
            self.canvas_settings.place(x=self.adapt_size(148), y=y)
            self.canvas_settings_show = True
            self.canvas_options.place_forget()
            self.canvas_options_show = False

    def setup_setting_window(self):
        self.canvas_settings = tk.Canvas(self, bg=self.glass_color, height=self.adapt_size(202),
                                         width=self.adapt_size(352), bd=0, highlightthickness=0)
        self.canvas_settings.place(x=self.adapt_size(148), y=self.adapt_size(self.abs_y - 214))
        self.canvas_settings.create_image(0, 0, image=self.set_img_tk, anchor=tk.NW)
        self.canvas_settings.place_forget()
        frame = self.setup_settings_inner_frame()
        button = DsButton(frame, width=self.adapt_size(60), height=self.adapt_size(26), bg='#262626', scale=self.scale)
        button.place(x=self.adapt_size(180), y=self.adapt_size(3))
        self.menus[6] = button
        self.canvas_settings.create_window(self.adapt_size(12), self.adapt_size(12), width=self.adapt_size(330),
                                           height=self.adapt_size(180), window=frame, anchor=tk.NW)

    def setup_settings_inner_frame(self):
        frame = tk.Frame(self, width=self.adapt_size(330), height=self.adapt_size(180), bd=1)
        label = tk.Label(frame, width=self.adapt_size(330), height=self.adapt_size(180), image=self.frame_img_tk)
        label.pack(fill=tk.BOTH, expand=True)
        self.select_sc_entry = tk.Entry(frame, font=('Arial', 8), disabledbackground='#872DE4',
                                        readonlybackground='#A283C0', foreground='black', textvariable=self.select_sc,
                                        relief=tk.FLAT, justify=tk.CENTER, disabledforeground='white', state='disabled')
        self.select_sc_entry.place(x=self.adapt_size(120), y=self.adapt_size(95), width=self.adapt_size(125))
        self.magic_sc_entry = tk.Entry(frame, font=('Arial', 8), disabledbackground='#872DE4',
                                       readonlybackground='#A283C0', foreground='black', textvariable=self.magic_sc,
                                       relief=tk.FLAT, justify=tk.CENTER, disabledforeground='white', state='disabled')
        self.magic_sc_entry.place(x=self.adapt_size(120), y=self.adapt_size(139), width=self.adapt_size(125))
        select_lock_btn = tk.Button(frame, image=self.lock_img_tk, textvariable=self.slb_var, relief=tk.FLAT,
                                    bg='#262626')
        select_lock_btn.place(x=self.adapt_size(260), y=self.adapt_size(95))
        magic_lock_btn = tk.Button(frame, image=self.lock_img_tk, textvariable=self.mlb_var, relief=tk.FLAT,
                                   bg='#262626')
        magic_lock_btn.place(x=self.adapt_size(260), y=self.adapt_size(139))
        self.menus[7] = select_lock_btn
        self.menus[8] = magic_lock_btn
        return frame

    def motion_bind(self):
        self.canvas.bind('<Button-1>', self.record_drag_first_point)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.position_display.bind('<Button-1>', self.record_drag_first_point)
        self.position_display.bind('<B1-Motion>', self.drag)
        threading.Thread(target=self.update_position, daemon=True).start()

    def record_drag_first_point(self, event):
        self.drag_first_point_x = event.x_root
        self.drag_first_point_y = event.y_root

    def drag(self, event):
        self.x_position = self.x_position + event.x_root - self.drag_first_point_x
        # 限制左边界
        if self.x_position < 0:
            self.x_position = 0
            self.y_position = self.y_position + event.y_root - self.drag_first_point_y
            self.geometry(f'+{self.x_position}+{self.y_position}')
            self.drag_first_point_x = event.x_root
            self.drag_first_point_y = event.y_root
            return
        self.y_position = self.y_position + event.y_root - self.drag_first_point_y

        # 限制右边界
        if self.x_position > self.winfo_screenwidth() - self.adapt_size(503) and event.x_root <= self.winfo_screenwidth():
            self.x_position = self.winfo_screenwidth() - self.adapt_size(503)
        # 限制上下边界
        if self.adapt_size(self.abs_y) + self.y_position < 0:
            self.y_position = 0 - self.adapt_size(self.abs_y)
        if self.y_position > self.winfo_screenheight() - self.taskbar_height - self.adapt_size(60 + self.abs_y):
            self.y_position = self.winfo_screenheight() - self.taskbar_height - self.adapt_size(60 + self.abs_y)
        self.geometry(f'+{self.x_position}+{self.y_position}')
        self.drag_first_point_x = event.x_root
        self.drag_first_point_y = event.y_root

    def update_position(self):
        while True:
            x, y = GetCursorPos()
            self.position_display_var.set(f'{x},{y}')
            time.sleep(0.05)

    def relative_to_assets(self, path: str) -> Path:
        return self.ASSETS_PATH / Path(path)


if __name__ == '__main__':
    import ctypes

    # ctypes.windll.shcore.SetProcessDpiAwareness(0)
    # ctypes.windll.user32.SetProcessDPIAware(1)
    ScaleFactor = ctypes.windll.shcore.GetScaleFactorForDevice(0)

    tool_panel = ToolPanel()
    tool_panel.tk.call('tk', 'scaling', ScaleFactor / 75)
    tool_panel.mainloop()
