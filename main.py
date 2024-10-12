import os

def check_config():
    if os.path.exists('config.ini'):
        pass
    else:
        str = '''[DEFAULT]
magic_mode = 1
select_shortcut_key = ALT+A
magic_shortcut_key = ALT+S
pointer = 1
recent_area = [(625,636),(1781,1107)]
recent_path = ~/Desktop
exit = 0'''
        with open('config.ini', 'w') as ob:
            ob.write(str)
check_config()

from mainwin import MainWindow
import ctypes

if __name__ == '__main__':
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    main_window = MainWindow()
    main_window.window_gradually_()
    main_window.mainloop()