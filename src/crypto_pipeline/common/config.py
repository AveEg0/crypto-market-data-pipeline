import os

CANDLES_TOPIC = "candles.1m"


def get_database_url() -> str:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url or not db_url.strip():
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in, "
            "and run via: uv run --env-file .env <command>"
        )
    return db_url


def get_kafka_bootstrap() -> str:
    value = os.environ.get("KAFKA_BOOTSTRAP")
    if not value:
        raise RuntimeError("KAFKA_BOOTSTRAP is not set. See .env.example")
    return value
