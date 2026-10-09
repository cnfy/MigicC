import time
import sys
import logging

from PIL import Image
import threading
import pystray
from win import ToolPanel
from settings import Settings
from pynput import keyboard
from shortcut import Shortcut
from listenqueue import start_queue
from version import DISPLAY_NAME

settings = Settings()
name = DISPLAY_NAME

class MainWindow(ToolPanel):
    def __init__(self):
        super().__init__()
        self.queue = start_queue(self)
        self._init_listener()
        self._init_font()
        self.create_menu()
        self.bind_menu()
        self.shortcut_win = None
        self.loading_settings()
        if getattr(sys, 'frozen', False) and settings.file_context_menu:
            from file_context import register_menu
            try:
                register_menu()
            except OSError:
                logging.getLogger(__name__).warning('Unable to register file context menu')
        from pcloud_client import start_cloud_cleanup
        start_cloud_cleanup(self)

    def _init_listener(self):
        self.sc_listener = keyboard.Listener(on_press=lambda e:self.queue.put(lambda:self.on_press(e, self.select_sc, 'sc')))
        self.mc_listener = keyboard.Listener(on_press=lambda e:self.queue.put(lambda:self.on_press(e, self.magic_sc, 'mc')))

    def on_press(self, key, vr, mo):
        new = None
        try:
            if key.char:
                old = vr.get()
                if len(old.split('+')) >= 3 or key.char in old.lower().split('+'):
                    return
                if old:
                    new = old + '+' + key.char
                else:
                    new = key.char
        except AttributeError:
            keyname = str(key).replace('Key.', '').replace('_l', '').replace('_gr', '').replace('_r', '')
            if key == keyboard.Key.enter:
                if mo == 'sc':
                    self.change_lock_btn_image_s()
                if mo == 'mc':
                    self.change_lock_btn_image_m()
            elif key == keyboard.Key.backspace:
                vr.set('')
            else:
                old = vr.get()
                if len(old.split('+')) >= 3 or keyname in old.lower().split('+'):
                    return
                if old:
                    new = old + '+' + keyname
                else:
                    new = keyname
        if new:
            vr.set(new.upper())

    def change_lock_btn_image_s(self):
        # self.slb_var: 0 is unlock, 1 is lock
        if self.slb_var.get():
            self.menus[7].config(image=self.unlock_img_tk)
            self.select_sc_entry.config(state='readonly')
            self.slb_var.set(0)
            if not self.mlb_var.get():
                self.mc_listener.stop()
                self.change_lock_btn_image_m()
                self._init_listener()
            self.sc_listener.start()
            self.lock_global_hotkeys()
        else:
            if not self.select_sc.get():
                self.select_sc.set(settings.select_shortcut_key)
            else:
                settings.update('select_shortcut_key', self.select_sc.get())
            self.menus[7].config(image=self.lock_img_tk)
            self.select_sc_entry.config(state='disabled')
            self.slb_var.set(1)
            self.sc_listener.stop()
            self._init_listener()
            self.update_global_hotkey()
            self.unlock_global_hotkeys()

    def change_lock_btn_image_m(self):
        # self.mlb_var: 0 is unlock, 1 is lock
        if self.mlb_var.get():
            self.menus[8].config(image=self.unlock_img_tk)
            self.magic_sc_entry.config(state='readonly')
            self.mlb_var.set(0)
            if not self.slb_var.get():
                self.sc_listener.stop()
                self.change_lock_btn_image_s()
                self._init_listener()
            self.mc_listener.start()
            self.lock_global_hotkeys()
        else:
            if not self.magic_sc.get():
                self.magic_sc.set(settings.magic_shortcut_key)
            else:
                settings.update('magic_shortcut_key', self.magic_sc.get())
            self.menus[8].config(image=self.lock_img_tk)
            self.magic_sc_entry.config(state='disabled')
            self.mlb_var.set(1)
            self.mc_listener.stop()
            self._init_listener()
            self.update_global_hotkey()
            self.unlock_global_hotkeys()

    def lock_global_hotkeys(self):
        self.unbind('<<select>>')
        self.unbind('<<magic>>')

    def unlock_global_hotkeys(self):
        self.bind('<<select>>', self.open_sub_window)
        self.bind('<<magic>>', self.magic_run)

    def update_global_hotkey(self):
        self.global_listener.stop()
        self._golbal_listener({
            self.parse_hotkey(settings.select_shortcut_key): self.select_callback,
            self.parse_hotkey(settings.magic_shortcut_key): self.magic_callback,
        })
        self.bind('<<select>>', self.open_sub_window)
        self.bind('<<magic>>', self.magic_run)
        self.global_listener.start()

    def _golbal_listener(self, hotkeys):
        self.global_listener = keyboard.GlobalHotKeys(hotkeys)

    def parse_hotkey(self, key):
        key_list = key.split('+')
        all = ''
        for item in key_list:
            if len(item) == 1:
                all += f'{item}+'
            else:
                all += f'<{item}>+'
        return all[:-1]

    def _init_font(self):
        self.font = ('Arial', 15, 'bold')

    def create_menu(self):
        menu = (pystray.MenuItem('Show', lambda *args:self.queue.put(self.show_window), default=True),
                pystray.MenuItem('文件二维码分享', lambda *args:self.queue.put(self.choose_share_file)),
                pystray.MenuItem('文件右键分享', lambda *args:self.queue.put(self.toggle_file_context_menu),
                                checked=lambda item: bool(settings.file_context_menu)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Exit', lambda *args:self.queue.put(self.quit_window)))
        image = Image.open(self.relative_to_assets('app.png'))
        self.pystray_icon = pystray.Icon('icon', image, name, menu)
        threading.Thread(target=self.pystray_icon.run, daemon=True).start()

    def choose_share_file(self):
        from tkinter import filedialog
        from qrshare import QRShareWindow
        path = filedialog.askopenfilename(parent=self, title='选择要分享的文件')
        if path:
            QRShareWindow(self, file_path=path, share_mode=settings.share_mode)

    def toggle_file_context_menu(self):
        from file_context import register_menu, unregister_menu
        from tkinter import messagebox
        enable = not settings.file_context_menu
        try:
            if enable:
                register_menu()
            else:
                unregister_menu()
            settings.update('file_context_menu', int(enable))
        except OSError:
            messagebox.showerror('文件右键分享', '无法更新文件右键菜单，请检查 Windows 用户权限。', parent=self)

    def show_window(self):
        self.deiconify()

    def quit_window(self, exit=1):
        if exit:
            self.global_listener.stop()
            self.sc_listener.stop()
            self.mc_listener.stop()
            self.pystray_icon.stop()
            self.destroy()
        else:
            self.withdraw()
            self.show_options()
            # self.show_settings()

    def bind_menu(self):
        self.menus.get(1).configure(command=self.open_sub_window)
        self.menus.get(2).configure(command=self.magic_run)
        self.menus.get(5).configure(command=lambda :self.quit_window(settings.exit))
        self.menus.get(6).config(command=lambda x:self.update_settings('magic_mode',x))
        self.menus.get(7).configure(command=self.change_lock_btn_image_s)
        self.menus.get(8).configure(command=self.change_lock_btn_image_m)
        self.menus[9].config(command=lambda value:self.update_settings('share_mode', value))
        self.menus[10].config(command=self.update_startup)

    def update_startup(self, enabled):
        from startup import set_enabled, is_enabled
        from tkinter import messagebox
        try:
            set_enabled(bool(enabled))
        except OSError:
            self.menus[10].setvalue(int(is_enabled()))
            messagebox.showerror('开机启动', '无法更新开机启动设置，请检查 Windows 用户权限。', parent=self)

    def open_sub_window(self, *args):
        if self.shortcut_win is None or not self.shortcut_win.isopened:
            self.shortcut_win = Shortcut(self, scale=self.scale, settings=settings)
            self.update()

    def update_settings(self, key, value):
        settings.update(key, value)

    def magic_run(self, *args):
        if self.shortcut_win is None or not self.shortcut_win.isopened:
            if settings.magic_mode:
                Shortcut.export_region(self, settings, settings.recent_area, save=True)
            else:
                Shortcut.export_region(self, settings, settings.recent_area, save=False)
        else:
            pass

    def loading_settings(self):
        self.menus[6].setvalue(int(settings.magic_mode)) # 0:clipboard ,1:save
        self.menus[9].setvalue(settings.share_mode)
        from startup import is_enabled
        self.menus[10].setvalue(int(is_enabled()))
        self.select_sc.set(settings.select_shortcut_key)
        self.magic_sc.set(settings.magic_shortcut_key)
        self.setup_global_hotkeys()

    def setup_global_hotkeys(self):
        self._golbal_listener({
            self.parse_hotkey(settings.select_shortcut_key): self.select_callback,
            self.parse_hotkey(settings.magic_shortcut_key): self.magic_callback,
        })
        self.bind('<<select>>', self.open_sub_window)
        self.bind('<<magic>>', self.magic_run)
        self.global_listener.start()

    def select_callback(self):
        self.queue.put(lambda :self.event_generate('<<select>>'))

    def magic_callback(self):
        self.queue.put(self.show_light_label)
        self.queue.put(lambda :self.event_generate('<<magic>>'))

    def show_light_label(self):
        self.light_label.place(x=self.adapt_size(87), y=self.adapt_size(self.abs_y + 2), width=self.adapt_size(58),
                               height=self.adapt_size(58))
        self.after(250, self.light_label.place_forget)

    def window_gradually_(self, mode='displays'):
        if mode == 'displays':
            for i in range(20):
                self.attributes('-alpha', (i+1) / 20)
                self.update()
                self.micro_sleep(0.003)
            self.attributes('-alpha', 1)
        elif mode == 'hide':
            for i in range(20):
                self.attributes('-alpha',1- (i+1) / 20)
                self.update()
                self.micro_sleep(0.003)
            self.attributes('-alpha', 0)

    def micro_sleep(self, sec):
        st = time.perf_counter()
        while time.perf_counter() - st < sec:
            pass
