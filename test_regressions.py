import ast
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from io import BytesIO
from urllib.request import urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from PIL import Image
from settings import Settings
from listenqueue import start_queue


def load_method(filename, class_name, method):
    tree = ast.parse(Path(filename).read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    function = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method)
    function.decorator_list = []
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), filename, 'exec'), namespace)
    return namespace[method]


class RegressionTests(unittest.TestCase):
    def test_cancel_consumes_release_before_closing_overlay(self):
        callbacks, closed = [], []
        owner = SimpleNamespace(after_idle=callbacks.append,
                                close_window=lambda event: closed.append(event))
        result = load_method('shortcut.py', 'Shortcut', 'cancel_release')(owner, object())
        self.assertEqual(result, 'break')
        self.assertEqual(closed, [])
        callbacks[0]()
        self.assertEqual(closed, [0])

    def test_qr_share_png_and_token(self):
        from qrshare import ScreenshotShare
        share = ScreenshotShare(Image.new('RGB', (9, 7), (80, 120, 200)), host='127.0.0.1')
        url = share.url('127.0.0.1')
        try:
            with urlopen(url, timeout=2) as response:
                self.assertIn(b'/download', response.read())
            with urlopen(url+'/image', timeout=2) as response:
                self.assertEqual(response.headers['Content-Type'], 'image/png')
                with Image.open(BytesIO(response.read())) as image:
                    self.assertEqual(image.size, (9, 7))
                    self.assertEqual(image.getpixel((0, 0)), (80, 120, 200))
            with urlopen(url+'/download', timeout=2) as response:
                self.assertIn('attachment', response.headers['Content-Disposition'])
            with self.assertRaises(HTTPError) as error:
                urlopen(url.rsplit('/', 1)[0]+'/invalid/image', timeout=2)
            self.assertEqual(error.exception.code, 404)
        finally:
            share.close()
            share.close()
        self.assertFalse(share.thread.is_alive())

    def test_original_pixels_and_monitor_offset(self):
        image = Image.new('RGB', (20, 20), (80, 120, 200))
        owner = SimpleNamespace(myscreen=SimpleNamespace(x=-100, y=50),
                                original_screen_image=image, mark_stack=[])
        result = load_method('shortcut.py', 'Shortcut', 'selected_image')(owner, (-98, 52), (-90, 60))
        self.assertEqual(result.size, (8, 8))
        self.assertEqual(result.getpixel((0, 0)), (80, 120, 200))

    def test_marks_drawn_on_original(self):
        owner = SimpleNamespace(myscreen=SimpleNamespace(x=0, y=0),
                    original_screen_image=Image.new('RGB', (20, 20), 'white'),
                    mark_stack=['mark1'], canvas=SimpleNamespace(coords=lambda tag:[3, 3, 8, 8]))
        result = load_method('shortcut.py', 'Shortcut', 'selected_image')(owner, (2, 2), (10, 10))
        self.assertEqual(result.getpixel((1, 1)), (255, 0, 0))
        self.assertEqual(result.getpixel((3, 3)), (255, 255, 255))

    def test_settings_validation_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(Path(directory)/'config.ini')
            settings.update('recent_area', "__import__('os').getcwd()")
            self.assertEqual(settings.recent_area, [(0, 0), (640, 480)])
            settings.update('gif_fps', 'invalid')
            self.assertEqual(settings.gif_fps, 10)
            settings.update('gif_max_seconds', 10000)
            self.assertEqual(settings.gif_max_seconds, 300)
            self.assertTrue(settings.path.exists())

    def test_user_directory_initialization_and_existing_settings(self):
        with tempfile.TemporaryDirectory() as directory, patch('settings.Path.home', return_value=Path(directory)):
            settings = Settings()
            self.assertEqual(settings.path, Path(directory)/'MagicC'/'config.ini')
            self.assertTrue(settings.path.is_file())
            self.assertIn('gif_fps = 10', settings.path.read_text(encoding='utf-8'))
            settings.update('gif_fps', 15)
            settings.update('magic_mode', 0)
            settings.update('share_mode', 0)
            reloaded = Settings()
            self.assertEqual(reloaded.gif_fps, 15)
            self.assertEqual(reloaded.magic_mode, 0)
            self.assertEqual(reloaded.share_mode, 0)

    def test_cloud_config_template_preserves_edits(self):
        from userconfig import ensure_cloud_config, open_cloud_config
        with tempfile.TemporaryDirectory() as directory, patch('userconfig.Path.home', return_value=Path(directory)):
            path = ensure_cloud_config()
            self.assertEqual(path, Path(directory)/'MagicC'/'.env')
            self.assertIn('PCLOUD_USERNAME=', path.read_text(encoding='utf-8'))
            self.assertIn('PCLOUD_PASSWORD=\n', path.read_text(encoding='utf-8'))
            path.write_text('PCLOUD_USERNAME=test@example.com\n', encoding='utf-8')
            ensure_cloud_config()
            self.assertEqual(path.read_text(encoding='utf-8'), 'PCLOUD_USERNAME=test@example.com\n')
            with patch('subprocess.Popen') as editor:
                open_cloud_config()
                editor.assert_called_once_with(['notepad.exe', str(path)])

    def test_share_mode_uses_explicit_choice(self):
        from qrshare import prepare_share
        from pcloud_client import PCloudError
        image = Image.new('RGB', (1, 1))
        with patch('pcloud_client.configured_client', return_value=None):
            with self.assertRaises(PCloudError):
                prepare_share(image, 0)
        with patch('qrshare.lan_address', return_value='127.0.0.1'), patch('qrshare.ScreenshotShare') as local, patch('pcloud_client.configured_client') as cloud:
            prepare_share(image, 1)
            local.assert_called_once_with(image)
            cloud.assert_not_called()

    def test_queue_runs_only_when_tk_polls(self):
        callbacks, results = [], []
        owner = SimpleNamespace(after=lambda ms, fn:callbacks.append(fn),
                                winfo_exists=lambda:True)
        queue = start_queue(owner)
        queue.put(lambda:results.append('done'))
        self.assertEqual(results, [])
        callbacks.pop(0)()
        self.assertEqual(results, ['done'])

    def test_one_frame_gif(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'single.gif'
            image = Image.new('RGB', (8, 8), (30, 120, 210)).quantize(colors=256)
            image.save(path, save_all=True, append_images=[], duration=[100], optimize=False)
            with Image.open(path) as saved:
                self.assertEqual(saved.convert('RGB').getpixel((0, 0)), (30, 120, 210))


if __name__ == '__main__':
    unittest.main()
