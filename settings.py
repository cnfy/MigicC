import configparser
import os.path
import ast
from pathlib import Path

DEFAULT_CONFIG = {
    'magic_mode': '1', 'select_shortcut_key': 'ALT+A',
    'magic_shortcut_key': 'ALT+S', 'pointer': '1',
    'recent_area': '[(0,0),(640,480)]', 'recent_path': '~/Desktop',
    'exit': '0', 'gif_fps': '10', 'gif_max_seconds': '30',
    'gif_countdown': '3',
    'share_mode': '1',  # 0: Cloud, 1: Local
}

class Settings:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else Path.home() / 'MagicC' / 'config.ini'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.config = configparser.ConfigParser(interpolation=None)
        self.config['DEFAULT'] = DEFAULT_CONFIG.copy()
        try:
            self.config.read(self.path, encoding='utf-8')
        except (configparser.Error, UnicodeError):
            pass
        self.loading()
        if not self.path.exists():
            self.write_config()

    def loading(self):
        self.magic_mode = self.number('magic_mode', 1, 0, 1)
        self.share_mode = self.number('share_mode', 1, 0, 1)
        self.select_shortcut_key = self.config['DEFAULT']['select_shortcut_key']
        self.magic_shortcut_key = self.config['DEFAULT']['magic_shortcut_key']
        self.pointer_show = self.number('pointer', 1, 0, 1)
        try:
            area = ast.literal_eval(self.config['DEFAULT']['recent_area'])
            assert len(area) == 2 and all(len(p) == 2 and all(type(v) is int for v in p) for p in area)
            assert area[1][0] > area[0][0] and area[1][1] > area[0][1]
            self.recent_area = [tuple(p) for p in area]
        except (SyntaxError, ValueError, TypeError, AssertionError, KeyError, IndexError):
            self.recent_area = [(0,0),(640,480)]
        self.gif_fps = self.number('gif_fps', 10, 1, 30)
        self.gif_max_seconds = self.number('gif_max_seconds', 30, 1, 300)
        self.gif_countdown = self.number('gif_countdown', 3, 0, 10)
        self.recent_path = os.path.expanduser(self.config['DEFAULT']['recent_path'])
        self.exit = self.number('exit', 0, 0, 1)

    def number(self, key, default, minimum, maximum):
        try:
            return max(minimum, min(maximum, int(self.config['DEFAULT'][key])))
        except (ValueError, TypeError):
            return default

    def update(self, key, value):
        self.config['DEFAULT'][key] = str(value)
        self.loading()
        self.write_config()

    def write_config(self):
        temporary = self.path.with_suffix('.ini.tmp')
        with temporary.open('w', encoding='utf-8') as configfile:
            self.config.write(configfile)
        temporary.replace(self.path)
