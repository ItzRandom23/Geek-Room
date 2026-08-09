from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path

from .config import get_settings


class AudioStorage:
    def __init__(self):
        self.settings = get_settings()
        self.backend = self.settings.storage_backend.lower()
        self.root = Path(self.settings.upload_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.client = None
        if self.backend == "s3":
            try:
                import boto3
                self.client = boto3.client("s3", region_name=self.settings.s3_region, endpoint_url=self.settings.s3_endpoint_url)
            except ImportError as exc:
                raise RuntimeError("S3 storage requires boto3. Install the backend requirements.") from exc

    def put(self, local_path: Path, key: str) -> None:
        if self.backend == "s3":
            if not self.client or not self.settings.s3_bucket:
                raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3.")
            self.client.upload_file(str(local_path), self.settings.s3_bucket, key, ExtraArgs={"ContentType": "audio/*"})

    def delete(self, key: str) -> None:
        if self.backend == "s3":
            if self.client and self.settings.s3_bucket:
                self.client.delete_object(Bucket=self.settings.s3_bucket, Key=key)
            return
        candidate = (self.root / Path(key).name).resolve()
        if candidate.parent == self.root:
            candidate.unlink(missing_ok=True)

    def signed_url(self, key: str) -> str | None:
        if self.backend != "s3" or not self.client or not self.settings.s3_bucket:
            return None
        return self.client.generate_presigned_url("get_object", Params={"Bucket": self.settings.s3_bucket, "Key": key}, ExpiresIn=300)

    @contextmanager
    def materialize(self, key: str):
        if self.backend != "s3":
            candidate = (self.root / Path(key).name).resolve()
            if candidate.parent != self.root or not candidate.exists():
                raise FileNotFoundError("Audio file not found")
            yield candidate
            return
        if not self.client or not self.settings.s3_bucket:
            raise FileNotFoundError("S3 audio storage is not configured")
        suffix = Path(key).suffix
        with tempfile.NamedTemporaryFile(prefix="pitsense-audio-", suffix=suffix, dir=self.root, delete=False) as handle:
            temporary = Path(handle.name)
        try:
            self.client.download_file(self.settings.s3_bucket, key, str(temporary))
            yield temporary
        finally:
            temporary.unlink(missing_ok=True)


def get_storage() -> AudioStorage:
    return AudioStorage()
