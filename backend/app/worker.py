"""RQ worker entrypoint for production deployments."""

from .config import get_settings


def main():
    settings = get_settings()
    if not settings.redis_url:
        raise SystemExit("REDIS_URL is required for the worker process.")
    from redis import Redis
    from rq import Queue, Worker
    connection = Redis.from_url(settings.redis_url)
    Worker([Queue("pitsense-analysis", connection=connection)], connection=connection).work()


if __name__ == "__main__":
    main()
