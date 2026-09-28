import os
import sys
from pathlib import Path

# Replace both paths with directories belonging to your HelioHost account.
APP_ROOT = Path('/home/REPLACE_WITH_HELIOHOST_USERNAME/ichu_app')
PRIVATE_DATA_DIR = Path('/home/REPLACE_WITH_HELIOHOST_USERNAME/ichu_data')
ENV_FILE = PRIVATE_DATA_DIR / '.env'

PRIVATE_DATA_DIR.mkdir(parents=True, exist_ok=True)
if ENV_FILE.is_file():
    for raw_line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, value = line.split('=', 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"\''))

os.environ.setdefault('ICHU_DATA_DIR', str(PRIVATE_DATA_DIR))
sys.path.insert(0, str(APP_ROOT))

from myapp import application
