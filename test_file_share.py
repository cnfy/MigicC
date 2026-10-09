from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from urllib.parse import quote
from unittest.mock import patch, Mock
import unittest

from qrshare import FileShare, prepare_file_share
from multipart_upload import MultipartUpload


class FileShareTests(unittest.TestCase):
    def test_local_download_original_bytes_and_unicode_name(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / '测试 & 文件.bin'
            payload = bytes(range(256)) * 8192
            path.write_bytes(payload)
            share = FileShare(path, host='127.0.0.1')
            url = share.url('127.0.0.1')
            try:
                with urlopen(url) as response:
                    self.assertIn('测试 &amp; 文件.bin', response.read().decode('utf-8'))
                with urlopen(url + '/download') as response:
                    self.assertIn(quote(path.name), response.headers['Content-Disposition'])
                    self.assertEqual(response.read(), payload)
                with urlopen(Request(url + '/download', method='HEAD')) as response:
                    self.assertEqual(int(response.headers['Content-Length']), len(payload))
                    self.assertEqual(response.read(), b'')
                with self.assertRaises(HTTPError):
                    urlopen(url + '/../../another-file')
            finally:
                share.close()
            self.assertFalse(share.thread.is_alive())

    def test_file_changed_or_deleted_download_not_found(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'file.txt'
            path.write_text('hello')
            share = FileShare(path, host='127.0.0.1')
            try:
                path.unlink()
                with self.assertRaises(HTTPError) as caught:
                    urlopen(share.url('127.0.0.1') + '/download')
                self.assertEqual(caught.exception.code, 404)
            finally:
                share.close()

    def test_folder_rejected(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                FileShare(directory)

    def test_file_cloud_uses_cloud_client(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'a.txt'
            path.write_text('hello')
            client = Mock()
            client.share_file.return_value = 'https://u.pcloud.link/test'
            with patch('pcloud_client.configured_client', return_value=client):
                self.assertEqual(prepare_file_share(path, 0),
                                 ('https://u.pcloud.link/test', True, 'https://u.pcloud.link/test'))
            client.share_file.assert_called_once_with(path.resolve())

    def test_multipart_stream_preserves_bytes_and_length(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'data.bin'
            payload = bytes(range(256)) * 1024
            path.write_bytes(payload)
            with path.open('rb') as source:
                body = MultipartUpload({'auth': 'test-token', 'folderid': 42},
                                       {'file': ('测试.bin', source, 'application/octet-stream')})
                output = BytesIO()
                while chunk := body.read(4096):
                    self.assertLessEqual(len(chunk), 4096)
                    output.write(chunk)
                result = output.getvalue()
                self.assertEqual(len(result), len(body))
                self.assertIn(payload, result)
                self.assertIn(b'test-token', result)
                self.assertIn('测试.bin'.encode(), result)
                self.assertTrue(result.endswith(f'--{body.boundary}--\r\n'.encode()))

    def test_explorer_command_quotes_paths(self):
        import file_context
        with patch('file_context.sys.executable', 'C:\\Program Files\\MagicC\\MagicC.exe'), \
                patch('file_context.sys.frozen', True, create=True):
            self.assertEqual(file_context.launch_command(),
                             '"C:\\Program Files\\MagicC\\MagicC.exe" --share-file "%1"')

    def test_upload_progress_counts_file_bytes_only(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'data.bin'
            payload = b'x' * 100000
            path.write_bytes(payload)
            updates = []
            with path.open('rb') as source:
                body = MultipartUpload({'auth': 'test-token'},
                                       {'file': ('data.bin', source, 'application/octet-stream')},
                                       progress=lambda sent, total: updates.append((sent, total)))
                while body.read(4096):
                    pass
            self.assertEqual(updates[-1], (len(payload), len(payload)))
            self.assertEqual([sent for sent, _ in updates], sorted(sent for sent, _ in updates))
            self.assertTrue(all(0 <= sent <= total for sent, total in updates))

    def test_cloud_progress_reaches_link_generation(self):
        from pcloud_client import PCloudClient
        responses = iter([{'result': 0, 'metadata': {'folderid': 42}},
                          {'result': 0, 'fileids': [123]},
                          {'result': 0, 'link': 'https://u.pcloud.link/test'}])

        def post(url, **kwargs):
            body = kwargs['data']
            if hasattr(body, 'read'):
                while body.read(4096):
                    pass
            result = Mock(status_code=200)
            result.json.return_value = next(responses)
            return result

        client = PCloudClient('u', 'p', session=Mock(post=post))
        client.auth = 'test-token'
        updates = []
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'file.bin'
            path.write_bytes(b'x' * 10000)
            client.share_file(path, progress=lambda *args: updates.append(args))
        self.assertEqual(updates[0][0], 'connecting')
        self.assertIn(('uploading', 10000, 10000), updates)
        self.assertEqual(updates[-1][0], 'processing')

    def test_cloud_close_deletes_only_shared_file_and_is_idempotent(self):
        from pcloud_client import CloudFileShare, PCloudClient
        with TemporaryDirectory() as directory, patch('cloud_cleanup.Path.home', return_value=Path(directory)):
            session = Mock()
            response = Mock(status_code=200)
            response.json.return_value = {'result': 0}
            session.post.return_value = response
            client = PCloudClient('u', 'p', session=session)
            client.auth = 'test-token'
            share = CloudFileShare('https://u.pcloud.link/test', client, 123)
            share.close()
            share.deletion_thread.join(5)
            share.close()
            self.assertEqual(session.post.call_count, 1)
            self.assertTrue(session.post.call_args.args[0].endswith('/deletefile'))
            self.assertEqual(session.post.call_args.kwargs['data']['fileid'], 123)
            from cloud_cleanup import pending
            self.assertEqual(pending(client.account_key), [])

    def test_failed_close_is_persisted_for_retry(self):
        from pcloud_client import CloudFileShare, PCloudError
        from cloud_cleanup import pending, complete
        with TemporaryDirectory() as directory, patch('cloud_cleanup.Path.home', return_value=Path(directory)):
            client = Mock(account_key='test-account')
            client.delete_file.side_effect = PCloudError('test network failure')
            share = CloudFileShare('https://u.pcloud.link/test', client, 123)
            with self.assertLogs('pcloud_client', level='WARNING'):
                share.close()
                share.deletion_thread.join(5)
            self.assertEqual(pending('test-account'), [123])
            self.assertEqual(pending('another-account'), [])
            complete('test-account', 123)
            self.assertEqual(pending('test-account'), [])


if __name__ == '__main__':
    unittest.main()
