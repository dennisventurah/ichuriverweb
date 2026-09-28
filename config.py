import os
import secrets

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///ichu.db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False