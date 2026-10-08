"""User-owned configuration paths and editable cloud credentials template."""
from pathlib import Path

ENV_TEMPLATE = '''# pCloud account settings (quote passwords containing spaces or #)
PCLOUD_USERNAME=
PCLOUD_PASSWORD=
# US: api.pcloud.com; Europe: eapi.pcloud.com
PCLOUD_API_HOST=api.pcloud.com
'''


def cloud_config_path():
    return Path.home() / 'MagicC' / '.env'


def ensure_cloud_config():
    path = cloud_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x', encoding='utf-8') as file:
            file.write(ENV_TEMPLATE)
    except FileExistsError:
        pass
    return path


def open_cloud_config():
    path = ensure_cloud_config()
    # Explicitly use Notepad: .env often has no Windows file association.
    import subprocess
    subprocess.Popen(['notepad.exe', str(path)])
