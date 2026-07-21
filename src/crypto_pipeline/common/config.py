import os


def get_database_url() -> str:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url or not db_url.strip():
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in, "
            "and run via: uv run --env-file .env <command>"
        )
    return db_url
