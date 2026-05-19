"""云存储抽象层 — 火山引擎 TOS"""
import os
import logging
from abc import ABC, abstractmethod
from typing import List

logger = logging.getLogger(__name__)


class CloudStorage(ABC):
    @abstractmethod
    def upload(self, local_path: str, remote_key: str) -> bool: ...

    @abstractmethod
    def download(self, remote_key: str, local_path: str) -> bool: ...

    @abstractmethod
    def delete_file(self, remote_key: str) -> bool: ...


class VolcengineTOSStorage(CloudStorage):
    def __init__(self, config: dict):
        import tos
        self.client = tos.TosClientV2(
            endpoint=config["endpoint"],
            region=config["region"],
            access_key_id=config["access_key_id"],
            access_key_secret=config["access_key_secret"],
        )
        self.bucket = config["bucket"]

    def upload(self, local_path: str, remote_key: str) -> bool:
        try:
            with open(local_path, "rb") as f:
                self.client.put_object(self.bucket, remote_key, f)
            logger.info("TOS upload: %s → %s", local_path, remote_key)
            return True
        except Exception:
            logger.exception("TOS upload failed: %s", remote_key)
            return False

    def download(self, remote_key: str, local_path: str) -> bool:
        try:
            resp = self.client.get_object(self.bucket, remote_key)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(resp.read())
            return True
        except Exception:
            logger.exception("TOS download failed: %s", remote_key)
            return False

    def delete_file(self, remote_key: str) -> bool:
        try:
            self.client.delete_object(self.bucket, remote_key)
            return True
        except Exception:
            logger.exception("TOS delete failed: %s", remote_key)
            return False


_storage = None


def get_cloud_storage() -> CloudStorage | None:
    global _storage
    if _storage is not None:
        return _storage
    from config.settings import TOS_CONFIG
    if not TOS_CONFIG.get("access_key_id") or not TOS_CONFIG.get("endpoint"):
        logger.warning("TOS 未配置，云存储功能不可用")
        return None
    _storage = VolcengineTOSStorage(TOS_CONFIG)
    return _storage
