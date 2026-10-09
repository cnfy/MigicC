from io import BytesIO
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from pcloud_client import PCloudClient, PCloudError


class PCloudTests(unittest.TestCase):
    def setUp(self):
        pending = patch('cloud_cleanup.pending', return_value=[])
        pending.start()
        self.addCleanup(pending.stop)

    def session(self, results):
        session = Mock()
        responses = []
        for result in results:
            response = Mock(status_code=200)
            response.json.return_value = result
            responses.append(response)
        session.post.side_effect = responses
        return session

    def test_upload_folder_png_link_and_reuse_token(self):
        session = self.session([{'result': 0, 'digest': 'test-digest'}, {'result': 0, 'auth': 'test-token'},
            {'result': 0, 'metadata': {'folderid': 42}}, {'result': 0, 'fileids': [123]},
            {'result': 0, 'link': 'https://my.pcloud.com/#page=publink&code=test'},
            {'result': 0, 'metadata': {'folderid': 42}}, {'result': 0, 'fileids': [124]},
            {'result': 0, 'link': 'https://my.pcloud.com/#page=publink&code=test2'}])
        client = PCloudClient('test@example.com', 'test-password', session=session)
        image = Image.new('RGB', (5, 6), (80, 120, 200))
        self.assertIn('code=test', client.share_image(image))
        client.share_image(image)
        calls = session.post.call_args_list
        self.assertEqual(calls[1].kwargs['data']['getauth'], 1)
        self.assertNotIn('password', calls[1].kwargs['data'])
        self.assertEqual(calls[2].kwargs['data']['name'], 'MagicC')
        self.assertEqual(calls[2].kwargs['data']['folderid'], 0)
        upload = calls[3].kwargs
        self.assertEqual(upload['data']['folderid'], 42)
        name, content, mime = upload['files']['file']
        self.assertTrue(name.endswith('.png'))
        self.assertEqual(mime, 'image/png')
        with Image.open(BytesIO(content)) as saved:
            self.assertEqual(saved.getpixel((0, 0)), (80, 120, 200))
        self.assertNotEqual(name, calls[6].kwargs['files']['file'][0])
        self.assertEqual(calls[4].kwargs['data']['fileid'], 123)
        self.assertEqual(calls[4].kwargs['data']['expire'], int(name.split('_')[2]))
        self.assertEqual(len(calls), 8)
        self.assertFalse(upload['allow_redirects'])
        self.assertEqual(upload['timeout'], (10, 60))

    def test_login_error_does_not_expose_credentials(self):
        session = self.session([{'result': 0, 'digest': 'test-digest'}, {'result': 2000, 'error': 'secret-test-password'}])
        client = PCloudClient('test@example.com', 'test-password', session=session)
        with self.assertRaises(PCloudError) as error:
            client.share_image(Image.new('RGB', (1, 1)))
        self.assertNotIn('test-password', str(error.exception))
        self.assertEqual(session.post.call_count, 2)

    def test_digest_without_auth_token(self):
        session = self.session([{'result': 0, 'digest': 'test-digest'}, {'result': 0},
            {'result': 0, 'metadata': {'folderid': 42}}, {'result': 0, 'fileids': [123]},
            {'result': 0, 'link': 'https://my.pcloud.com/#page=publink&code=test'}])
        client = PCloudClient('TEST@example.com', 'test-password', session=session)
        client.share_image(Image.new('RGB', (1, 1)))
        for call in session.post.call_args_list[2:]:
            self.assertEqual(call.kwargs['data']['username'], 'test@example.com')
            self.assertEqual(call.kwargs['data']['digest'], 'test-digest')
            self.assertEqual(len(call.kwargs['data']['passworddigest']), 40)
            self.assertNotIn('password', call.kwargs['data'])
            self.assertNotIn('auth', call.kwargs['data'])

    def test_host_validation(self):
        with self.assertRaises(PCloudError):
            PCloudClient('user', 'password', host='untrusted.example.com')

    @patch('pcloud_client.time.time', return_value=1800000000)
    def test_cleanup_only_expired_managed_files(self, clock):
        items = [
            {'name': 'magicc_share_1800000000_abcdef012345.png', 'fileid': 1},
            {'name': 'magicc_share_1800000001_abcdef012345.png', 'fileid': 2},
            {'name': 'screenshot_20261009_old.png', 'fileid': 3},
            {'name': 'personal.png', 'fileid': 4},
            {'name': 'magicc_share_1700000000_abcdef012345.png', 'fileid': 5, 'isfolder': True},
            {'name': 'magicc_file_1800000000_abcdef012345_文档.pdf', 'fileid': 6}]
        session = self.session([{'result': 0, 'digest': 'd'}, {'result': 0, 'auth': 't'},
                                {'result': 0, 'metadata': {'contents': items}}, {'result': 0}, {'result': 0}])
        client = PCloudClient('u', 'p', session=session)
        self.assertEqual(client.cleanup_expired(), 2)
        self.assertEqual(session.post.call_args.kwargs['data']['fileid'], 6)
        self.assertEqual(session.post.call_args_list[2].kwargs['data']['path'], '/MagicC')

    def test_cleanup_network_failure_can_retry(self):
        session = self.session([{'result': 0, 'digest': 'd'}, {'result': 0, 'auth': 't'},
                                {'result': 5000}, {'result': 0, 'digest': 'd2'},
                                {'result': 0, 'auth': 't2'},
                                {'result': 0, 'metadata': {'contents': []}}])
        client = PCloudClient('u', 'p', session=session)
        with self.assertRaises(PCloudError):
            client.cleanup_expired()
        self.assertIsNone(client.auth)
        self.assertEqual(client.cleanup_expired(), 0)

    def test_expiry_rejection_rolls_back_upload(self):
        session = self.session([{'result': 0, 'digest': 'd'}, {'result': 0, 'auth': 't'},
                                {'result': 0, 'metadata': {'folderid': 42}},
                                {'result': 0, 'fileids': [123]}, {'result': 2003}, {'result': 0}])
        client = PCloudClient('u', 'p', session=session)
        with self.assertRaises(PCloudError):
            client.share_image(Image.new('RGB', (1, 1)))
        self.assertTrue(session.post.call_args.args[0].endswith('/deletefile'))
        self.assertEqual(session.post.call_args.kwargs['data']['fileid'], 123)

    def test_basic_account_uses_app_cleanup(self):
        session = self.session([{'result': 0, 'digest': 'd'},
                                {'result': 0, 'auth': 't', 'premium': False},
                                {'result': 0, 'metadata': {'folderid': 42}},
                                {'result': 0, 'fileids': [123]},
                                {'result': 0, 'link': 'https://u.pcloud.link/test'}])
        client = PCloudClient('u', 'p', session=session)
        client.share_image(Image.new('RGB', (1, 1)))
        self.assertFalse(client.supports_expiry)
        self.assertNotIn('expire', session.post.call_args.kwargs['data'])

    def test_partial_configuration(self):
        with patch('pcloud_client.cloud_config_path', return_value='.env'), patch('pcloud_client.dotenv_values', return_value={'PCLOUD_USERNAME': 'test@example.com'}), patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(PCloudError):
                PCloudClient.from_env()

    def test_no_configuration(self):
        with patch('pcloud_client.cloud_config_path', return_value='.env'), patch('pcloud_client.dotenv_values', return_value={}), patch.dict('os.environ', {}, clear=True):
            self.assertIsNone(PCloudClient.from_env())


if __name__ == '__main__':
    unittest.main()
