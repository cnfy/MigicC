"""Build native Explorer command, signed identity package, and per-user Setup EXE.

Run fetch_build_tools.py first. Signing material stays in ignored .signing/.
The default certificate is for local testing, not a publicly trusted publisher.
"""
from pathlib import Path
import datetime
import shutil
import subprocess
import secrets
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from PIL import Image

ROOT = Path(__file__).resolve().parent


def run(args):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def build():
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    compiler = next((ROOT / '.build-tools/llvm').glob('*/bin/x86_64-w64-mingw32-clang++.exe'))
    sdk = next((ROOT / '.build-tools/sdk/bin').glob('*/x64/makeappx.exe')).parent
    nsis = next((ROOT / '.build-tools/nsis').glob('*/makensis.exe'))
    run([compiler, '-std=c++17', '-O2', '-shared', '-static', '-o', dist / 'MagicCShell.dll',
         ROOT / 'shell/MagicCShell.cpp', ROOT / 'shell/MagicCShell.def',
         '-lole32', '-lshell32', '-lshlwapi', '-luuid'])
    package = ROOT / 'build/menu-package'
    (package / 'Assets').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'shell/AppxManifest.xml', package / 'AppxManifest.xml')
    with Image.open(ROOT / 'media/app.png') as icon:
        for name, size in [('StoreLogo', 50), ('Square150', 150), ('Square44', 44)]:
            icon.convert('RGBA').resize((size, size)).save(package / f'Assets/{name}.png')
    signing = ROOT / '.signing'
    signing.mkdir(exist_ok=True)
    pfx_path = signing / 'MagicC.pfx'
    password_path = signing / 'password'
    cert_path = signing / 'MagicC.cer'
    if not pfx_path.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'MagicC Local Build')])
        now = datetime.datetime.now(datetime.timezone.utc)
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                       .public_key(key.public_key()).serial_number(x509.random_serial_number())
                       .not_valid_before(now - datetime.timedelta(days=1))
                       .not_valid_after(now + datetime.timedelta(days=365 * 3))
                       .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                       .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CODE_SIGNING]), critical=False)
                       .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), critical=True)
                       .sign(key, hashes.SHA256()))
        password = secrets.token_urlsafe(32)
        password_path.write_text(password, encoding='ascii')
        pfx_path.write_bytes(pkcs12.serialize_key_and_certificates(
            b'MagicC', key, certificate, None, serialization.BestAvailableEncryption(password.encode())))
        cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.DER))
    shutil.copyfile(cert_path, dist / 'MagicC.cer')
    shutil.copyfile(ROOT / 'media/app.ico', dist / 'MagicC.ico')
    for script in ('menu.ps1', 'trust.ps1'):
        (dist / script).write_text((ROOT / 'installer' / script).read_text(encoding='utf-8'), encoding='utf-8-sig')
    run([sdk / 'makeappx.exe', 'pack', '/o', '/nv', '/d', package, '/p', dist / 'MagicC.Menu.msix'])
    # Never print the signing password or the full signing command.
    result = subprocess.run([str(sdk / 'signtool.exe'), 'sign', '/fd', 'SHA256', '/f', str(pfx_path),
                             '/p', password_path.read_text(encoding='ascii'), str(dist / 'MagicC.Menu.msix')])
    if result.returncode:
        raise RuntimeError('Package signing failed; the signing command is intentionally redacted.')
    run([nsis, '/INPUTCHARSET', 'UTF8', ROOT / 'installer/MagicC.nsi'])


if __name__ == '__main__':
    build()
