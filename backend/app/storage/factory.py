from __future__ import annotations

from app.config import Settings
from app.storage.kdb import KdbStorage
from app.storage.local import LocalCsvStorage


def create_storage(settings: Settings):
    if settings.storage_backend == "kdb":
        return KdbStorage(
            settings.kdb_host,
            settings.kdb_port,
            username=settings.kdb_username,
            password=settings.kdb_password,
        )
    if settings.storage_backend == "local":
        return LocalCsvStorage(settings.local_data_dir)
    raise ValueError(f"Unknown storage backend: {settings.storage_backend}")

