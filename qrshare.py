"""Temporary, token-protected LAN sharing for a single PNG screenshot."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import secrets
import socket
import threading
from queue import Queue, Empty
from pathlib import Path
import tkinter as tk
import html
import shutil
from urllib.parse import quote
from tkinter import messagebox
from tkinter import ttk

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


class FileShare(ScreenshotShare):
    """Serve one selected file in chunks, without loading it into memory."""
    def __init__(self, path, host='0.0.0.0'):
        path = Path(path).resolve(strict=True)
        if not path.is_file():
            raise ValueError('请选择一个文件，暂不支持文件夹。')
        # Check access before opening the sharing window.
        with path.open('rb'):
            pass
        self.token = secrets.token_urlsafe(24)
        base = '/' + self.token
        page = ('<!doctype html><html lang="zh"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>MagicC 文件分享</title><body style="font-family:sans-serif;text-align:center">'
                '<h2>' + html.escape(path.name) + '</h2>'
                '<p><a href="' + base + '/download">下载文件</a></p>'
                '<p>关闭电脑上的分享窗口后，链接失效。</p></body></html>').encode('utf-8')

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.serve()

            def do_HEAD(self):
                self.serve(head=True)

            def serve(self, head=False):
                if self.path in (base, base + '/'):
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(page)))
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    if not head:
                        self.wfile.write(page)
                    return
                if self.path != base + '/download':
                    self.send_error(404)
                    return
                try:
                    source = path.open('rb')
                except OSError:
                    self.send_error(404, 'File unavailable')
                    return
                with source:
                    import os
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.send_header('Content-Length', str(os.fstat(source.fileno()).st_size))
                    self.send_header('Content-Disposition',
                                     "attachment; filename=download; filename*=UTF-8''" + quote(path.name))
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.end_headers()
                    if not head:
                        try:
                            shutil.copyfileobj(source, self.wfile, length=64 * 1024)
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


def prepare_file_share(path, share_mode, progress=None):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError('请选择一个文件，暂不支持文件夹。')
    if share_mode == 0:
        from pcloud_client import configured_client, PCloudError
        client = configured_client()
        if client is None:
            raise PCloudError('请点击设置里的 Cloud，填写 pCloud 用户名和密码并保存。')
        link = client.share_file(path, progress=progress) if progress else client.share_file(path)
        return link, True, link
    address = lan_address()
    share = FileShare(path)
    return share.url(address), False, share


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
    def __init__(self, master, image=None, screen=None, share_mode=1, file_path=None):
        super().__init__(master)
        self.withdraw()
        self.share = None
        self.screen = screen
        self.results = Queue()
        self.pending = True
        self.progress_update = None
        self.bind('<Destroy>', self.cleanup)
        self.file_path = Path(file_path) if file_path is not None else None
        self.item_type = '文件' if self.file_path is not None else '截图'
        self.title('扫码获取' + self.item_type)
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
        self.loading = tk.Label(self.content, text='正在准备分享…', padx=28, pady=20,
                                **self.label_style)
        self.loading.pack()
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('MagicC.Horizontal.TProgressbar', background='#D45BE0',
                        troughcolor='#353039', bordercolor='#353039',
                        lightcolor='#D45BE0', darkcolor='#D45BE0')
        self.progress_bar = ttk.Progressbar(self.content, length=340,
                                           style='MagicC.Horizontal.TProgressbar',
                                           mode='indeterminate')
        self.progress_bar.pack(padx=24, pady=(0, 12))
        self.progress_bar.start(15)
        self.progress_detail = tk.Label(self.content, text='', **self.label_style)
        self.progress_detail.pack(padx=24, pady=(0, 16))
        self.center_window()
        self.deiconify()
        def prepare():
            try:
                self.results.put(prepare_file_share(self.file_path, share_mode,
                                                   progress=self.report_progress)
                                 if self.file_path is not None else prepare_share(image, share_mode))
            except Exception as error:
                self.results.put(error)
        # Finish outstanding requests before process exit; Tk itself is never touched here.
        threading.Thread(target=prepare, daemon=False).start()
        self.after(50, self.poll_share)

    def report_progress(self, stage, sent, total):
        # A single coalesced update; uploading threads never access Tk widgets.
        self.progress_update = (stage, sent, total)

    def update_progress(self):
        update = self.progress_update
        if update is None:
            return
        self.progress_update = None
        stage, sent, total = update
        if stage == 'uploading':
            self.progress_bar.stop()
            self.progress_bar.configure(mode='determinate', maximum=max(1, total),
                                        value=sent if total else 1)
            percent = min(100, sent * 100 / total) if total else 100
            self.loading.configure(text=f'正在上传… {percent:.0f}%')
            self.progress_detail.configure(text=f'{sent / 1048576:.1f} / {total / 1048576:.1f} MB')
        elif stage == 'processing':
            self.progress_bar.stop()
            self.progress_bar.configure(mode='determinate', maximum=100, value=100)
            self.loading.configure(text='上传完成，正在生成分享链接…')
        else:
            self.loading.configure(text='正在连接 pCloud…')

    def poll_share(self):
        self.update_progress()
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
        self.progress_bar.stop()
        self.progress_bar.destroy()
        self.progress_detail.destroy()
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
        self.title('扫码获取' + self.item_type)
        self.resizable(False, False)
        self.attributes('-topmost', True)
        tk.Label(self.content, text='手机扫码获取' + self.item_type, font=('Microsoft YaHei', 14),
                 bg='#262626', fg='white').pack(pady=(16, 4))
        qr_frame = tk.Frame(self.content, bg='#D45BE0', padx=3, pady=3)
        qr_frame.pack(padx=20, pady=8)
        tk.Label(qr_frame, image=self.qr_image, bg='white', bd=0).pack()
        if self.file_path is not None:
            tk.Label(self.content, text=self.file_path.name, wraplength=380,
                     **self.label_style).pack(padx=20, pady=4)
        save_hint = '点击下载按钮保存文件' if self.file_path is not None else '长按图片或点击保存按钮，即可保存 PNG'
        cloud_hint = ('关闭分享窗口后立即删除云端副本\n断网时将在下次启动联网后清理' if self.file_path is not None else
                      '截图 24 小时后自动清理\n请保持程序运行并联网；关闭后下次启动清理')
        instructions = ('已上传到 pCloud /MagicC\n' + cloud_hint if cloud else
                        '手机与电脑需在同一局域网\n' + save_hint + '\n关闭窗口或 10 分钟后，分享链接失效')
        tk.Label(self.content, text=instructions, **self.label_style).pack(padx=20, pady=8)
        tk.Label(self.content, text=('持有二维码或分享链接的人可以访问此' + self.item_type if cloud else '无法打开时，请检查 Windows 防火墙的专用网络访问权限'),
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
            try:
                self.progress_bar.stop()
            except tk.TclError:
                pass  # The loading widgets may already have been destroyed.
            if self.share is not None:
                self.share.close()
            # If closed during preparation, wait off the UI thread and close any LAN server.
            if self.pending:
                def finish():
                    result = self.results.get()
                    if isinstance(result, tuple) and result[2] is not None:
                        result[2].close()
                threading.Thread(target=finish, daemon=False).start()
