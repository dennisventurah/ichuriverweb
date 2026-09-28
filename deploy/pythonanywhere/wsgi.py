import os
import sys
from pathlib import Path

# Clone the repository to ~/ichuriverweb on PythonAnywhere.
PROJECT_HOME = Path.home() / 'ichuriverweb'
PRIVATE_DATA_DIR = Path.home() / '.local' / 'share' / 'ichuriverweb'
PRIVATE_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Keep the database and secrets outside the directory mapped to the website.
os.environ.setdefault('ICHU_DATA_DIR', str(PRIVATE_DATA_DIR))
ENV_FILE = PRIVATE_DATA_DIR / '.env'
if ENV_FILE.is_file():
    for raw_line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, value = line.split('=', 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"\''))

if str(PROJECT_HOME) not in sys.path:
    sys.path.insert(0, str(PROJECT_HOME))

from app import app as application
