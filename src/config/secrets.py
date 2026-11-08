import os
from dotenv import load_dotenv

load_dotenv()


class SECRETS:
    DB_NAME: str = ""
    DB_USER: str = ""
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_PASSWORD: str = ""

    @classmethod
    def load_secrets(cls):
        cls.DB_NAME = os.getenv("DB_NAME", "")
        cls.DB_USER = os.getenv("DB_USER", "")
        cls.DB_HOST = os.getenv("DB_HOST", "localhost")
        cls.DB_PORT = int(os.getenv("DB_PORT", 5432))
        cls.DB_PASSWORD = os.getenv("DB_PASSWORD", "")
        print("Secrets loaded successfully.")
