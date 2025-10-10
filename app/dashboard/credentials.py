import os
from pathlib import Path
from dotenv import load_dotenv


def get():
    current_path = Path(__file__)
    server_path = current_path.parent.parent.parent
    env_path = server_path / "env/.env"
    load_dotenv(dotenv_path=env_path)
    db_user = os.getenv("DASH_DB_USER")
    db_password = os.getenv("DASH_DB_PASSWORD")
    user = os.getenv("DASH_USER")
    password = os.getenv("DASH_PASSWORD")

    return db_user, db_password, user, password
