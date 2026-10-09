"""Download portable build tools from their publishers into an ignored directory."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen
import json
import zipfile
import hashlib

ROOT = Path(__file__).parent / '.build-tools'
ROOT.mkdir(exist_ok=True)

def get_json(url):
    with urlopen(Request(url, headers={'User-Agent': 'MagicC-build'}), timeout=60) as response:
        return json.load(response)

def download(url, target, digest=None):
    if not target.exists():
        with urlopen(Request(url, headers={'User-Agent': 'MagicC-build'}), timeout=60) as response, target.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    if digest and digest.startswith('sha256:'):
        with target.open('rb') as source:
            assert hashlib.file_digest(source, 'sha256').hexdigest() == digest[7:], 'Download checksum mismatch'

def llvm():
    release = get_json('https://api.github.com/repos/mstorsjo/llvm-mingw/releases/latest')
    asset = next(item for item in release['assets'] if item['name'].endswith('-ucrt-x86_64.zip'))
    archive = ROOT / asset['name']
    download(asset['browser_download_url'], archive, asset.get('digest'))
    with zipfile.ZipFile(archive) as package:
        package.extractall(ROOT / 'llvm')
    print('LLVM-mingw ready', flush=True)

def sdk():
    base = 'https://api.nuget.org/v3-flatcontainer/microsoft.windows.sdk.buildtools/'
    versions = get_json(base + 'index.json')['versions']
    version = next(v for v in reversed(versions) if v.startswith('10.0.26100.') and '-' not in v)
    archive = ROOT / 'sdk.zip'
    download(base + version + '/microsoft.windows.sdk.buildtools.' + version + '.nupkg', archive)
    with zipfile.ZipFile(archive) as package:
        package.extractall(ROOT / 'sdk')
    print('Windows SDK tools ready', flush=True)

def nsis():
    archive = ROOT / 'nsis.zip'
    download('https://downloads.sourceforge.net/project/nsis/NSIS%203/3.11/nsis-3.11.zip', archive)
    with zipfile.ZipFile(archive) as package:
        package.extractall(ROOT / 'nsis')
    print('NSIS ready', flush=True)

with ThreadPoolExecutor(max_workers=3) as pool:
    futures = [pool.submit(task) for task in (llvm, sdk, nsis)]
    for future in futures:
        future.result()
