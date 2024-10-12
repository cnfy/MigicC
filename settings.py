import configparser
import os.path

class Settings:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.loading()

    def loading(self):
        self.magic_mode = int(self.config['DEFAULT']['magic_mode'])
        self.select_shortcut_key = self.config['DEFAULT']['select_shortcut_key']
        self.magic_shortcut_key = self.config['DEFAULT']['magic_shortcut_key']
        self.pointer_show = int(self.config['DEFAULT']['pointer'])
        self.recent_area = eval(self.config['DEFAULT']['recent_area'])
        self.recent_path = os.path.expanduser(self.config['DEFAULT']['recent_path'])
        self.exit = int(self.config['DEFAULT']['exit'])

    def update(self, key, value):
        self.config['DEFAULT'][key] = str(value)
        self.loading()
        with open('config.ini','w') as configfile:
            self.config.write(configfile)