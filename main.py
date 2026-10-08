import ctypes

if __name__ == '__main__':
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, 'Local\\MagicC.SingleInstance')
    if kernel.GetLastError() == 183:
        raise SystemExit(0)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()
    from mainwin import MainWindow
    main_window = MainWindow()
    main_window.window_gradually_()
    main_window.mainloop()
