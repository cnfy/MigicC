"""pCloud account authentication and screenshot sharing; no secrets in logs."""
import time
import re
import logging
from io import BytesIO
from hashlib import sha1
import os
import threading
import uuid
from urllib.parse import urlparse

from dotenv import dotenv_values
import requests
from userconfig import cloud_config_path


class PCloudError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


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

    def request(self, method, data, files=None):
        try:
            response = self.session.post(f'https://{self.host}/{method}', data=data,
                                         files=files, timeout=(10, 60), allow_redirects=False)
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

    def call(self, method, data, files=None):
        credentials = {'auth': self.auth} if self.auth else self.digest_params
        if not credentials:
            raise PCloudError('尚未完成 pCloud 认证。')
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
        with self.lock:
            self.authenticate()
            try:
                folder = self.call('createfolderifnotexists', {'folderid': 0, 'name': 'MagicC'})
                folderid = folder['metadata']['folderid']
                expires = int(time.time()) + 24 * 60 * 60
                name = f'magicc_share_{expires}_{uuid.uuid4().hex[:12]}.png'
                output = BytesIO()
                image.convert('RGB').save(output, 'PNG')
                uploaded = self.call('uploadfile', {'folderid': folderid, 'nopartial': 1, 'renameifexists': 1},
                                     {'file': (name, output.getvalue(), 'image/png')})
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
                return link
            except PCloudError:
                # Refresh on the next explicit attempt, without automatically retrying uploads.
                self.auth = None
                self.digest_params = None
                raise
            except (KeyError, IndexError, TypeError):
                raise PCloudError('pCloud 返回数据缺少文件夹、文件或分享链接信息。') from None

    def cleanup_expired(self):
        """Delete only this version's managed PNGs in /MagicC, never old files."""
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
                    match = re.fullmatch(r'magicc_share_(\d{10})_[0-9a-f]{12}\.png', item.get('name', ''))
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
        except PCloudError as error:
            logging.getLogger(__name__).warning('Cloud cleanup postponed: %s', error)
        finally:
            running.clear()

    def tick():
        if not running.is_set():
            running.set()
            threading.Thread(target=sweep, daemon=True).start()
        owner.after(60_000, tick)

    owner.after(0, tick)
