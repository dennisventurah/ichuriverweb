import os
import secrets
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv('ICHU_DATA_DIR', PROJECT_DIR)).expanduser().resolve()

class Config:
    # Configure SECRET_KEY in the hosting environment for stable sessions.
    # The random fallback is only for local development and does not touch disk.
    SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_hex(32)

    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f"sqlite:///{(DATA_DIR / 'ichu.db').as_posix()}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False