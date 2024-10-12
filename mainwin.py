import time

from PIL import Image
import threading
import pystray
from win import ToolPanel
from settings import Settings
from pynput import keyboard
from shortcut import Shortcut
from listenqueue import start_queue

settings = Settings()
name = 'MagicCamera ver_bate 0.1'

class MainWindow(ToolPanel):
    def __init__(self):
        super().__init__()
        self._init_listener()
        self._init_font()
        self.create_menu()
        self.bind_menu()
        self.shortcut_win = Shortcut(self,self.scale,settings)
        self.shortcut_win.close_window(0)
        self.loading_settings()

    def _init_listener(self):
        self.sc_listener = keyboard.Listener(on_press=lambda e:self.on_press(e, self.select_sc, 'sc'))
        self.mc_listener = keyboard.Listener(on_press=lambda e:self.on_press(e, self.magic_sc, 'mc'))

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
            keyname = str(key).replace('Key,', '').replace('_l', '').replace('_gr', '').replace('_r', '')
            if key == keyboard.Key.enter:
                if mo == 'sc':
                    self.change_lock_btn_image_s()
                if mo == 'mc':
                    self.change_lock_btn_image_m()
            elif key == keyboard.Key.backspace:
                vr.set('')
            else:
                old = vr.get()
                if len(old.split('+')) >= 3 or key.char in old.lower().split('+'):
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
        menu = (pystray.MenuItem('Show', self.show_window, default=True), pystray.Menu.SEPARATOR,
                pystray.MenuItem('Exit', self.quit_window))
        image = Image.open(self.relative_to_assets('app.png'))
        self.pystray_icon = pystray.Icon('icon', image, name, menu)
        threading.Thread(target=self.pystray_icon.run, daemon=True).start()

    def show_window(self):
        self.deiconify()

    def quit_window(self, exit=1):
        if exit:
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

    def open_sub_window(self, *args):
        if not self.shortcut_win.isopened:
            self.shortcut_win = Shortcut(self, scale=self.scale, settings=settings)
            self.update()

    def update_settings(self, key, value):
        settings.update(key, value)

    def magic_run(self, *args):
        if not self.shortcut_win.isopened:
            if settings.magic_mode:
                self.shortcut_win.save_shortcut(settings.recent_area[0],settings.recent_area[1])
            else:
                self.shortcut_win.send_shortcut(settings.recent_area[0],settings.recent_area[1])
        else:
            pass

    def loading_settings(self):
        self.menus[6].setvalue(int(settings.magic_mode)) # 0:clipboard ,1:save
        self.select_sc.set(settings.select_shortcut_key)
        self.magic_sc.set(settings.magic_shortcut_key)
        self.setup_global_hotkeys()

    def setup_global_hotkeys(self):
        self.queue = start_queue()
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
        time.sleep(0.25)
        self.light_label.place_forget()

    def window_gradually_(self, mode='dispalys'):
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