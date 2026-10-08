"""Run the source with dependencies installed in .runtime-deps."""
from pathlib import Path
import runpy
import site

root = Path(__file__).resolve().parent
site.addsitedir(str(root / '.runtime-deps'))
runpy.run_path(str(root / 'main.py'), run_name='__main__')
