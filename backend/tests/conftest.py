"""Keep automated API tests isolated from the local judge database.

The application defaults to ``backend/pitsense.db`` for a convenient local
demo. Tests must never append their temporary sessions and accounts to that
database, because those rows would appear in the judge-facing dashboard.
"""

import os
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parents[1]
TEST_DB = TEST_ROOT / "pitsense_test.db"
TEST_UPLOADS = TEST_ROOT / "test-uploads"

# Set these before any test imports app.database, which constructs the engine
# from the cached Settings object.
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["UPLOAD_DIR"] = str(TEST_UPLOADS)
os.environ["AUTO_MIGRATE"] = "true"
os.environ["AUTH_REQUIRED"] = "false"


def _remove_test_artifacts() -> None:
    # SQLite may leave sidecar files while a connection is closing.
    for path in (TEST_DB, Path(f"{TEST_DB}-wal"), Path(f"{TEST_DB}-shm")):
        path.unlink(missing_ok=True)
    if TEST_UPLOADS.exists():
        for child in TEST_UPLOADS.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                import shutil

                shutil.rmtree(child, ignore_errors=True)
        TEST_UPLOADS.rmdir()


def pytest_sessionstart(session):  # noqa: ARG001 - pytest hook signature
    _remove_test_artifacts()


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001 - pytest hook signature
    try:
        from app.database import engine

        engine.dispose()
    finally:
        _remove_test_artifacts()
