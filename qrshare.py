"""Temporary, token-protected LAN sharing for a single PNG screenshot."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import secrets
import socket
import threading
from queue import Queue, Empty
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import qrcode
from PIL import ImageTk


def lan_address():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            # Route lookup only: UDP connect does not transmit a packet.
            sock.connect(('192.0.2.1', 80))
            address = sock.getsockname()[0]
        except OSError:
            address = socket.gethostbyname(socket.gethostname())
    if address.startswith('127.') or address == '0.0.0.0':
        raise OSError('未找到局域网地址，请先连接 Wi-Fi 或有线网络。')
    return address


class ScreenshotShare:
    def __init__(self, image, host='0.0.0.0'):
        output = BytesIO()
        image.save(output, format='PNG')
        payload = output.getvalue()
        self.token = secrets.token_urlsafe(24)
        base = '/' + self.token
        page = ('<!doctype html><html lang="zh"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>截图</title><body style="font-family:sans-serif;text-align:center">'
                '<h2>电脑截图</h2><p><a href="' + base + '/download">保存 PNG 图片</a></p>'
                '<p>也可以长按图片保存。关闭电脑上的二维码窗口后，链接失效。</p>'
                '<img style="max-width:100%;height:auto" src="' + base + '/image">'
                '</body></html>').encode('utf-8')

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == base or self.path == base + '/':
                    body, content_type = page, 'text/html; charset=utf-8'
                elif self.path in (base + '/image', base + '/download'):
                    body, content_type = payload, 'image/png'
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                if self.path.endswith('/download'):
                    self.send_header('Content-Disposition', 'attachment; filename="screenshot.png"')
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer((host, 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': 0.05}, daemon=True)
        self.thread.start()
        self.closed = False

    def url(self, address):
        return f'http://{address}:{self.server.server_port}/{self.token}'

    def close(self):
        if not self.closed:
            self.closed = True
            self.server.shutdown()
            self.server.server_close()


def prepare_share(image, share_mode):
    if share_mode == 0:
        from pcloud_client import configured_client, PCloudError
        client = configured_client()
        if client is None:
            raise PCloudError('请点击设置里的 Cloud，填写 pCloud 用户名和密码并保存。')
        return client.share_image(image), True, None
    address = lan_address()
    share = ScreenshotShare(image)
    return share.url(address), False, share


class QRShareWindow(tk.Toplevel):
    def __init__(self, master, image, screen=None, share_mode=1):
        super().__init__(master)
        self.withdraw()
        self.share = None
        self.screen = screen
        self.results = Queue()
        self.pending = True
        self.bind('<Destroy>', self.cleanup)
        self.title('扫码获取截图')
        self.iconbitmap(str(Path(__file__).parent / 'media' / 'app.ico'))
        self.configure(bg='#D45BE0')
        self.surface = tk.Canvas(self, bg='#D45BE0', bd=0, highlightthickness=0)
        self.surface.pack(fill='both', expand=True)
        self.surface.bind('<Configure>', self.draw_surface)
        self.content = tk.Frame(self.surface, bg='#262626')
        # Keep rectangular child widgets clear of the rounded corners.
        self.content.pack(fill='both', expand=True, padx=16, pady=16)
        self.label_style = dict(bg='#262626', fg='white', font=('Microsoft YaHei', 10))
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.loading = tk.Label(self.content, text='正在准备分享…', padx=60, pady=60,
                                **self.label_style)
        self.loading.pack()
        self.center_window()
        self.deiconify()
        def prepare():
            try:
                self.results.put(prepare_share(image, share_mode))
            except Exception as error:
                self.results.put(error)
        # Finish outstanding requests before process exit; Tk itself is never touched here.
        threading.Thread(target=prepare, daemon=False).start()
        self.after(50, self.poll_share)

    def poll_share(self):
        try:
            result = self.results.get_nowait()
        except Empty:
            self.after(50, self.poll_share)
            return
        self.pending = False
        if isinstance(result, Exception):
            messagebox.showerror('二维码分享失败', str(result), parent=self)
            self.destroy()
            return
        url, cloud, self.share = result
        self.loading.destroy()
        try:
            qr = qrcode.QRCode(box_size=7, border=4)
            qr.add_data(url)
            qr.make(fit=True)
            self.qr_image = ImageTk.PhotoImage(qr.make_image().convert('RGB'), master=self)
        except Exception as error:
            messagebox.showerror('二维码分享失败', str(error), parent=self)
            self.destroy()
            return
        self.title('扫码获取截图')
        self.resizable(False, False)
        self.attributes('-topmost', True)
        tk.Label(self.content, text='手机扫码获取截图', font=('Microsoft YaHei', 14),
                 bg='#262626', fg='white').pack(pady=(16, 4))
        qr_frame = tk.Frame(self.content, bg='#D45BE0', padx=3, pady=3)
        qr_frame.pack(padx=20, pady=8)
        tk.Label(qr_frame, image=self.qr_image, bg='white', bd=0).pack()
        instructions = ('已上传到 pCloud /MagicC\n截图 24 小时后自动清理\n请保持程序运行并联网；关闭后下次启动清理' if cloud else
                        '手机与电脑需在同一局域网\n长按图片或点击保存按钮，即可保存 PNG\n关闭窗口或 10 分钟后，分享链接失效')
        tk.Label(self.content, text=instructions, **self.label_style).pack(padx=20, pady=8)
        tk.Label(self.content, text=('持有二维码或分享链接的人可以访问这张截图' if cloud else '无法打开时，请检查 Windows 防火墙的专用网络访问权限'),
                 wraplength=380, bg='#262626', fg='#C5B2DF',
                 font=('Microsoft YaHei', 10)).pack(padx=16, pady=4)
        entry = tk.Entry(self.content, width=60, bg='#353039', readonlybackground='#353039',
                         fg='white', selectbackground='#872DE4', selectforeground='white',
                         relief=tk.FLAT, highlightthickness=1,
                         highlightbackground='#9778E9', highlightcolor='#D45BE0')
        entry.insert(0, url)
        entry.configure(state='readonly')
        entry.pack(padx=16, pady=8)
        tk.Button(self.content, text='关闭分享', command=self.destroy,
                  bg='#872DE4', fg='white', activebackground='#B642CA',
                  activeforeground='white', relief=tk.FLAT, bd=0,
                  font=('Microsoft YaHei', 10), padx=22, pady=6,
                  cursor='hand2').pack(pady=(4, 16))
        self.center_window()
        self.after(10*60*1000, self.destroy)

    def draw_surface(self, event):
        inset, radius = 3, 14
        left, top = inset, inset
        right, bottom = event.width - inset, event.height - inset
        points = (left + radius, top, right - radius, top,
                  right, top, right, top + radius,
                  right, bottom - radius, right, bottom,
                  right - radius, bottom, left + radius, bottom,
                  left, bottom, left, bottom - radius,
                  left, top + radius, left, top)
        self.surface.delete('surface')
        self.surface.create_polygon(points, smooth=True, splinesteps=24,
                                    fill='#262626', outline='', tags='surface')
        self.surface.tag_lower('surface')

    def center_window(self):
        self.update_idletasks()
        from win32api import GetMonitorInfo, MonitorFromPoint, GetCursorPos
        screen = self.screen
        point = (screen.x + screen.width//2, screen.y + screen.height//2) if screen else GetCursorPos()
        left, top, right, bottom = GetMonitorInfo(MonitorFromPoint(point, 2))['Work']
        # Center against the monitor work area, not the floating toolbar parent.
        # Leave room for the native title bar and borders.
        width = min(self.winfo_reqwidth(), max(1, right-left-32))
        height = min(self.winfo_reqheight(), max(1, bottom-top-64))
        x = left + (right-left-width)//2
        y = top + (bottom-top-height-32)//2
        self.geometry(f'{width}x{height}+{x}+{y}')

    def cleanup(self, event):
        if event.widget is self:
            if self.share is not None:
                self.share.close()
            # If closed during preparation, wait off the UI thread and close any LAN server.
            if self.pending:
                def finish():
                    result = self.results.get()
                    if isinstance(result, tuple) and result[2] is not None:
                        result[2].close()
                threading.Thread(target=finish, daemon=True).start()
