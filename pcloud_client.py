"""pCloud account authentication and screenshot sharing; no secrets in logs."""
import time
import re
import logging
import sqlite3
from io import BytesIO
from hashlib import sha1, sha256
import os
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values
import requests
from userconfig import cloud_config_path


class PCloudError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class CloudFileShare(str):
    def __new__(cls, link, client, fileid):
        instance = super().__new__(cls, link)
        instance.client, instance.fileid = client, fileid
        instance.closed = False
        return instance

    def close(self):
        if self.closed:
            return
        self.closed = True
        from cloud_cleanup import enqueue
        try:
            enqueue(self.client.account_key, self.fileid)
        except Exception:
            logging.getLogger(__name__).warning('Could not persist cloud deletion request')
        def remove():
            try:
                self.client.delete_file(self.fileid)
            except (PCloudError, OSError, sqlite3.Error):
                logging.getLogger(__name__).warning('Cloud file deletion postponed until network recovery')
        # Finish deletion even when closing the standalone sharing process.
        self.deletion_thread = threading.Thread(target=remove, daemon=False)
        self.deletion_thread.start()


class PCloudClient:
    def __init__(self, username, password, host='api.pcloud.com', session=None):
        if host not in ('api.pcloud.com', 'eapi.pcloud.com'):
            raise PCloudError('PCLOUD_API_HOST 只能为 api.pcloud.com 或 eapi.pcloud.com。')
        self.username, self.password = username, password
        self.host = host
        self.session = session or requests.Session()
        self.auth = None
        self.digest_params = None
        self.supports_expiry = True
        self.lock = threading.Lock()
        self.account_key = sha256((host + '\n' + username.lower()).encode()).hexdigest()

    @classmethod
    def from_env(cls):
        values = {**dotenv_values(cloud_config_path(), encoding='utf-8-sig'), **os.environ}
        username = (values.get('PCLOUD_USERNAME') or '').strip()
        password = values.get('PCLOUD_PASSWORD') or ''
        if not username and not password:
            return None
        if not username or not password:
            raise PCloudError('请点击设置里的 Cloud，在用户目录 .env 中填写用户名和密码并保存。')
        return cls(username, password, (values.get('PCLOUD_API_HOST') or 'api.pcloud.com').strip())

    def request(self, method, data, files=None, progress=None):
        try:
            headers = None
            if files and any(hasattr(item[1], 'read') for item in files.values()):
                from multipart_upload import MultipartUpload
                data = MultipartUpload(data, files, progress=progress)
                headers = {'Content-Type': data.content_type}
                files = None
            response = self.session.post(f'https://{self.host}/{method}', data=data,
                                         files=files, headers=headers,
                                         timeout=(10, 60), allow_redirects=False)
            response.raise_for_status()
            if response.status_code != 200:
                raise PCloudError('pCloud 返回了非预期 HTTP 状态。')
            result = response.json()
        except (requests.RequestException, ValueError):
            # requests exceptions can include URLs or request details; never expose them.
            raise PCloudError('pCloud 网络请求失败，请检查网络、数据中心和稍后重试。') from None
        if not isinstance(result, dict):
            raise PCloudError('pCloud 返回格式异常。')
        if result.get('result') != 0:
            code = result.get('result')
            messages = {1000: '登录已失效，请重试。', 1022: 'pCloud 要求提供 code 参数，当前认证请求未被接受。', 2000: '登录失败，请检查账号密码和数据中心；启用双重验证的账号可能需要其他认证方式。',
                        2014: '请先在 pCloud 验证账号邮箱。', 4000: '登录尝试过多，请稍后再试。'}
            raise PCloudError(messages.get(code, f'pCloud 操作失败（错误码 {code}）。'), code=code)
        return result

    def call(self, method, data, files=None, progress=None):
        credentials = {'auth': self.auth} if self.auth else self.digest_params
        if not credentials:
            raise PCloudError('尚未完成 pCloud 认证。')
        if progress is not None:
            result = self.request(method, {**data, **credentials}, files, progress=progress)
        else:
            result = self.request(method, {**data, **credentials}, files)
        return result

    def authenticate(self):
        if not self.auth:
            # Authenticate with the server challenge instead of sending the password.
            digest = self.request('getdigest', {}).get('digest')
            if not isinstance(digest, str) or not digest:
                raise PCloudError('pCloud 未返回摘要认证信息。')
            username = self.username.lower()
            self.digest_params = {'username': username, 'digest': digest,
                'passworddigest': sha1(self.password.encode('utf-8') +
                    sha1(username.encode('utf-8')).hexdigest().encode('ascii') +
                    digest.encode('utf-8')).hexdigest()}
            result = self.request('userinfo', {**self.digest_params, 'getauth': 1, 'device': 'MagicC'})
            self.auth = result.get('auth')
            self.supports_expiry = result.get('premium', True)
            # Some responses omit auth despite success. Authenticate each call
            # using the digest instead; refresh the digest on each new share.

    def share_image(self, image):
        output = BytesIO()
        image.convert('RGB').save(output, 'PNG')
        return self.share_upload(output.getvalue(), 'image/png')

    def share_file(self, path, progress=None):
        path = Path(path).resolve(strict=True)
        if not path.is_file():
            raise PCloudError('请选择一个文件，暂不支持文件夹。')
        with path.open('rb') as source:
            return self.share_upload(source, 'application/octet-stream', path.name, progress=progress)

    def share_upload(self, source, mime, filename=None, progress=None):
        if progress:
            progress('connecting', 0, 0)
        with self.lock:
            self.authenticate()
            try:
                folder = self.call('createfolderifnotexists', {'folderid': 0, 'name': 'MagicC'})
                folderid = folder['metadata']['folderid']
                expires = int(time.time()) + 24 * 60 * 60
                identifier = uuid.uuid4().hex[:12]
                name = (f'magicc_file_{expires}_{identifier}_{filename}' if filename is not None
                        else f'magicc_share_{expires}_{identifier}.png')
                upload_args = ({'folderid': folderid, 'nopartial': 1, 'renameifexists': 1},
                               {'file': (name, source, mime)})
                if progress:
                    progress('uploading', 0, os.fstat(source.fileno()).st_size)
                    uploaded = self.call('uploadfile', *upload_args,
                                         progress=lambda sent, total: progress('uploading', sent, total))
                    progress('processing', 0, 0)
                else:
                    uploaded = self.call('uploadfile', *upload_args)
                fileid = uploaded['fileids'][0]
                try:
                    link_params = {'fileid': fileid}
                    if self.supports_expiry:
                        link_params['expire'] = expires
                    try:
                        shared = self.call('getfilepublink', link_params)
                    except PCloudError as error:
                        if error.code != 2261:
                            raise
                        self.supports_expiry = False
                        shared = self.call('getfilepublink', {'fileid': fileid})
                except PCloudError:
                    # Do not leave an unshared upload behind when expiry is rejected.
                    try:
                        self.call('deletefile', {'fileid': fileid})
                    except PCloudError:
                        pass  # The periodic sweep still finds this managed file.
                    raise
                link = shared['link']
                parsed = urlparse(link)
                if parsed.scheme != 'https' or parsed.hostname not in ('my.pcloud.com', 'u.pcloud.link', 'e.pcloud.link', 'www.pcloud.com'):
                    raise PCloudError('pCloud 返回了非预期分享链接。')
                return CloudFileShare(link, self, fileid) if filename is not None else link
            except PCloudError:
                # Refresh on the next explicit attempt, without automatically retrying uploads.
                self.auth = None
                self.digest_params = None
                raise
            except (KeyError, IndexError, TypeError):
                raise PCloudError('pCloud 返回数据缺少文件夹、文件或分享链接信息。') from None

    def delete_file(self, fileid):
        from cloud_cleanup import complete
        with self.lock:
            try:
                self.authenticate()
                try:
                    self.call('deletefile', {'fileid': fileid})
                except PCloudError as error:
                    if error.code != 2009:
                        raise
            except PCloudError:
                self.auth = None
                self.digest_params = None
                raise
        complete(self.account_key, fileid)

    def cleanup_expired(self):
        """Delete only managed uploads in /MagicC, never unrelated files."""
        from cloud_cleanup import pending
        for fileid in pending(self.account_key):
            self.delete_file(fileid)
        with self.lock:
            try:
                self.authenticate()
                try:
                    folder = self.call('listfolder', {'path': '/MagicC', 'recursive': 0})
                except PCloudError as error:
                    if error.code == 2005:  # Folder does not exist yet.
                        return 0
                    raise
                deleted = 0
                now = int(time.time())
                for item in folder['metadata']['contents']:
                    match = re.fullmatch(r'magicc_(?:share|file)_(\d{10})_[0-9a-f]{12}(?:\.png|_.+)', item.get('name', ''))
                    if item.get('isfolder') or not match or int(match[1]) > now:
                        continue
                    try:
                        self.call('deletefile', {'fileid': item['fileid']})
                    except PCloudError as error:
                        if error.code != 2009:  # Already removed on another device.
                            raise
                    deleted += 1
                return deleted
            except PCloudError:
                self.auth = None
                self.digest_params = None
                raise
            except (KeyError, TypeError):
                raise PCloudError('pCloud 清理返回格式异常。') from None


_client = None
_config = None

def configured_client():
    global _client, _config
    candidate = PCloudClient.from_env()
    config = None if candidate is None else (candidate.username, candidate.password, candidate.host)
    if config != _config:
        _client, _config = candidate, config
    return _client


def start_cloud_cleanup(owner):
    """Sweep on startup and every minute, without blocking Tk or overlapping jobs."""
    running = threading.Event()

    def sweep():
        try:
            client = configured_client()
            if client is not None:
                client.cleanup_expired()
        except (PCloudError, OSError, sqlite3.Error) as error:
            logging.getLogger(__name__).warning('Cloud cleanup postponed: %s', error)
        finally:
            running.clear()

    def tick():
        if not running.is_set():
            running.set()
            threading.Thread(target=sweep, daemon=True).start()
        owner.after(60_000, tick)

    owner.after(0, tick)
