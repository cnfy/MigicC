import ctypes
import sys

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] in ('--enable-startup', '--disable-startup'):
        from startup import set_enabled
        set_enabled(sys.argv[1] == '--enable-startup')
        raise SystemExit(0)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()
    if len(sys.argv) == 3 and sys.argv[1] == '--share-file':
        from file_context import share_file_window
        share_file_window(sys.argv[2])
        raise SystemExit(0)
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateEventW.restype = ctypes.c_void_p
    kernel.SetEvent.argtypes = [ctypes.c_void_p]
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    show_event = kernel.CreateEventW(None, False, False, 'Local\\MagicC.ShowWindow')
    mutex = kernel.CreateMutexW(None, False, 'Local\\MagicC.SingleInstance')
    if kernel.GetLastError() == 183:
        if '--startup' not in sys.argv:
            kernel.SetEvent(show_event)
        raise SystemExit(0)
    from mainwin import MainWindow
    main_window = MainWindow()
    if '--startup' in sys.argv:
        main_window.withdraw()
    else:
        main_window.deiconify()
        main_window.window_gradually_()
    def check_show_request():
        if kernel.WaitForSingleObject(show_event, 0) == 0:
            main_window.show_window()
        main_window.after(1000, check_show_request)
    main_window.after(1000, check_show_request)
    main_window.mainloop()
