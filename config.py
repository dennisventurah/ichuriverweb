import os
import secrets
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv('ICHU_DATA_DIR', PROJECT_DIR)).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)


def persistent_secret_key():
    secret_path = DATA_DIR / '.secret_key'
    try:
        return secret_path.read_text(encoding='utf-8').strip()
    except FileNotFoundError:
        generated = secrets.token_hex(32)
        try:
            descriptor = os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return secret_path.read_text(encoding='utf-8').strip()
        with os.fdopen(descriptor, 'w', encoding='utf-8') as secret_file:
            secret_file.write(generated)
        return generated

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or persistent_secret_key()

    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f"sqlite:///{(DATA_DIR / 'ichu.db').as_posix()}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False