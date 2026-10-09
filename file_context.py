"""Per-user Explorer context menu and standalone file sharing entry point."""
from pathlib import Path
import subprocess
import sys
import winreg
import ctypes

MENU_KEY = r'Software\Classes\*\shell\MagicCShare'


def refresh_shell():
    # Flush association changes instead of leaving an asynchronous notification.
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x1003, None, None)
    notify = ctypes.windll.user32.SendMessageTimeoutW
    notify.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t,
                       ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_uint,
                       ctypes.POINTER(ctypes.c_size_t)]
    notify.restype = ctypes.c_void_p
    result = ctypes.c_size_t()
    # Broadcast WM_SETTINGCHANGE without hanging on unresponsive applications.
    notify(0xFFFF, 0x001A, 0, 'Software\\Classes', 0x0002, 1000, ctypes.byref(result))


def launch_command():
    if getattr(sys, 'frozen', False):
        args = [sys.executable]
    else:
        args = [sys.executable, str(Path(__file__).parent / 'run_local.py')]
    return subprocess.list2cmdline(args) + ' --share-file "%1"'


def modern_install_directory():
    if getattr(sys, 'frozen', False):
        directory = Path(sys.executable).parent
        if (directory / 'menu.ps1').is_file() and (directory / 'MagicC.Menu.msix').is_file():
            return directory
    return None


def update_modern_menu(action):
    directory = modern_install_directory()
    if directory is None:
        return
    result = subprocess.run(
        ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive',
         '-ExecutionPolicy', 'Bypass', '-File', str(directory / 'menu.ps1'),
         '-Action', action], creationflags=subprocess.CREATE_NO_WINDOW,
        capture_output=True, timeout=120)
    if result.returncode:
        raise OSError('无法更新 Windows 11 右键菜单，请重新运行安装包。')


def register_menu():
    directory = modern_install_directory()
    if directory and (directory / 'modern-menu.enabled').exists():
        # Already installed: avoid PowerShell/package registration at each boot.
        refresh_shell()
        return
    if directory and (directory / 'certificate.imported').exists():
        update_modern_menu('Register')
        refresh_shell()
        return
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, MENU_KEY) as key:
        winreg.SetValueEx(key, '', 0, winreg.REG_SZ, '用 MagicC 二维码分享')
        winreg.SetValueEx(key, 'MUIVerb', 0, winreg.REG_SZ, '用 MagicC 二维码分享')
        try:
            winreg.DeleteValue(key, 'Position')
        except FileNotFoundError:
            pass
        icon = sys.executable if getattr(sys, 'frozen', False) else str(Path(__file__).parent / 'media' / 'app.ico')
        winreg.SetValueEx(key, 'Icon', 0, winreg.REG_SZ, subprocess.list2cmdline([icon]))
        winreg.SetValueEx(key, 'MultiSelectModel', 0, winreg.REG_SZ, 'Single')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, MENU_KEY + r'\command') as key:
        winreg.SetValueEx(key, '', 0, winreg.REG_SZ, launch_command())
    refresh_shell()


def unregister_menu():
    directory = modern_install_directory()
    if directory and (directory / 'modern-menu.enabled').exists():
        update_modern_menu('Unregister')
    for path in (MENU_KEY + r'\command', MENU_KEY):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        except FileNotFoundError:
            pass
    refresh_shell()


def share_file_window(path):
    import tkinter as tk
    from tkinter import messagebox
    from settings import Settings
    from qrshare import QRShareWindow

    root = tk.Tk()
    root.withdraw()
    try:
        selected = Path(path).resolve(strict=True)
        if not selected.is_file():
            raise ValueError('请选择一个文件，暂不支持文件夹。')
        window = QRShareWindow(root, file_path=selected, share_mode=Settings().share_mode)
        root.wait_window(window)
    except (OSError, ValueError) as error:
        messagebox.showerror('文件分享失败', str(error), parent=root)
    finally:
        root.destroy()
