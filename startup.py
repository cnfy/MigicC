"""Current-user startup registration; boot launches are tray-only."""
from pathlib import Path
import subprocess
import sys
import winreg

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE_NAME = 'MagicC'


def startup_command():
    if getattr(sys, 'frozen', False):
        args = [sys.executable]
    else:
        interpreter = Path(sys.executable)
        pythonw = interpreter.with_name('pythonw.exe')
        args = [str(pythonw if pythonw.exists() else interpreter),
                str(Path(__file__).parent / 'run_local.py')]
    return subprocess.list2cmdline(args + ['--startup'])


def is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except FileNotFoundError:
        return False


def set_enabled(enabled):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
