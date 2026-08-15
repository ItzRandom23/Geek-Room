"""Vercel entrypoint for the PitSense FastAPI backend."""

import os


# Vercel functions may only write to /tmp. These fallbacks make preview
# deployments boot without configuration; production must use Postgres and S3.
if os.getenv("VERCEL"):
    os.environ.setdefault("UPLOAD_DIR", "/tmp/pitsense-uploads")
    os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/pitsense.db")

from app.main import app  # noqa: E402,F401
