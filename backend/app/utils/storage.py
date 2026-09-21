"""Private document storage; object keys never become public download URLs.

Every adapter uses the exact canonical key supplied by the document service;
the service is responsible for including the configured storage prefix.
The local adapter requires POSIX ``dir_fd``/``O_NOFOLLOW`` support (Linux/macOS).
Cloud SDK imports are deferred until the corresponding backend is selected.
"""

from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Protocol
from uuid import uuid4

from app.utils.document_errors import DocumentError

if TYPE_CHECKING:
    from app.core.config import Settings


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def check(self) -> None: ...


def _configuration_error() -> DocumentError:
    return DocumentError(
        "STORAGE_CONFIGURATION_ERROR", "Document storage is not configured correctly.", 503
    )


def _unavailable() -> DocumentError:
    return DocumentError("STORAGE_UNAVAILABLE", "Document storage is unavailable.", 503)


def _not_found() -> DocumentError:
    return DocumentError("FILE_NOT_FOUND", "The stored document was not found.", 404)


def _validate_key(key: str) -> list[str]:
    # Validate the original string: Path/PurePath would normalize away unsafe parts.
    if not isinstance(key, str) or not key or "\\" in key or "\x00" in key:
        raise _configuration_error()
    parts = key.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise _configuration_error()
    return parts


class LocalStorage:
    """Atomically store files beneath a private, configured local directory.

    Directory-relative operations and O_NOFOLLOW prevent intermediate or final
    symlinks from redirecting an operation outside the opened storage directory.
    Missing deletes are idempotent, matching S3/OSS delete semantics.
    """

    def __init__(self, root: Path) -> None:
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            raise _configuration_error()
        try:
            self.root = Path(root).expanduser().resolve()
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        except (OSError, RuntimeError):
            raise _unavailable() from None

    @contextmanager
    def _parent(self, parts: list[str], *, create: bool = False) -> Iterator[int]:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptors: list[int] = []
        try:
            current = os.open(self.root, flags)
            descriptors.append(current)
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=current)
                    except FileExistsError:
                        pass
                current = os.open(part, flags, dir_fd=current)
                descriptors.append(current)
            yield current
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    @staticmethod
    def _regular_file(parent: int, name: str) -> None:
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            raise _unavailable()

    def put(self, key: str, data: bytes, content_type: str) -> None:
        parts = _validate_key(key)
        try:
            with self._parent(parts, create=True) as parent:
                try:
                    self._regular_file(parent, parts[-1])
                except FileNotFoundError:
                    pass
                temporary = f".upload-{uuid4().hex}"
                descriptor = os.open(
                    temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600, dir_fd=parent,
                )
                try:
                    with os.fdopen(descriptor, "wb") as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
                finally:
                    try:
                        os.unlink(temporary, dir_fd=parent)
                    except FileNotFoundError:
                        pass
        except OSError:
            raise _unavailable() from None

    def get(self, key: str) -> bytes:
        parts = _validate_key(key)
        try:
            with self._parent(parts) as parent:
                descriptor = os.open(
                    parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
                )
                with os.fdopen(descriptor, "rb") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        raise _unavailable()
                    return stream.read()
        except FileNotFoundError:
            raise _not_found() from None
        except OSError:
            raise _unavailable() from None

    def delete(self, key: str) -> None:
        parts = _validate_key(key)
        try:
            with self._parent(parts) as parent:
                self._regular_file(parent, parts[-1])
                os.unlink(parts[-1], dir_fd=parent)
        except FileNotFoundError:
            return
        except OSError:
            raise _unavailable() from None

    def check(self) -> None:
        key = f".readiness-{uuid4().hex}"
        data = b"document-storage-readiness"
        try:
            self.put(key, data, "application/octet-stream")
            if self.get(key) != data:
                raise _unavailable()
        finally:
            self.delete(key)


class S3Storage:
    """AWS S3 or an S3-compatible endpoint, with the default AWS credential chain."""

    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.storage_bucket.strip()
        access_key = settings.storage_access_key_id.get_secret_value()
        secret_key = settings.storage_access_key_secret.get_secret_value()
        token = settings.storage_session_token.get_secret_value()
        if not self.bucket or bool(access_key) != bool(secret_key) or (token and not access_key):
            raise _configuration_error()
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise _configuration_error() from None
        options: dict = {
            "config": Config(
                connect_timeout=settings.storage_timeout_seconds,
                read_timeout=settings.storage_timeout_seconds,
                retries={"mode": "standard", "total_max_attempts": 3},
            )
        }
        if settings.storage_region:
            options["region_name"] = settings.storage_region
        if settings.storage_endpoint:
            options["endpoint_url"] = settings.storage_endpoint
        if access_key:
            options.update(aws_access_key_id=access_key, aws_secret_access_key=secret_key)
            if token:
                options["aws_session_token"] = token
        try:
            self.client = boto3.client("s3", **options)
        except Exception:
            raise _configuration_error() from None

    def _key(self, key: str) -> str:
        _validate_key(key)
        return key

    def put(self, key: str, data: bytes, content_type: str) -> None:
        object_key = self._key(key)
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=object_key, Body=data, ContentType=content_type
            )
        except Exception:
            raise _unavailable() from None

    def get(self, key: str) -> bytes:
        object_key = self._key(key)
        try:
            result = self.client.get_object(Bucket=self.bucket, Key=object_key)
            body = result["Body"]
            try:
                return body.read()
            finally:
                body.close()
        except Exception as error:
            response = getattr(error, "response", {})
            code = response.get("Error", {}).get("Code") if isinstance(response, dict) else None
            if code in {"NoSuchKey", "NoSuchObject", "NotFound", "404"}:
                raise _not_found() from None
            raise _unavailable() from None

    def delete(self, key: str) -> None:
        object_key = self._key(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=object_key)
        except Exception:
            raise _unavailable() from None

    def check(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            raise _unavailable() from None


class OSSStorage:
    """Alibaba Cloud OSS using an explicit AccessKey pair or temporary STS token."""

    def __init__(self, settings: Settings) -> None:
        bucket = settings.storage_bucket.strip()
        access_key = settings.storage_access_key_id.get_secret_value()
        secret_key = settings.storage_access_key_secret.get_secret_value()
        token = settings.storage_session_token.get_secret_value()
        if not bucket or not settings.storage_endpoint or not access_key or not secret_key:
            raise _configuration_error()
        try:
            import oss2
        except ImportError:
            raise _configuration_error() from None
        try:
            # Signature V4 requires the region; retain V1 for older configurations.
            if token:
                auth = oss2.StsAuth(
                    access_key, secret_key, token,
                    auth_version="v4" if settings.storage_region else "v1",
                )
            else:
                auth_class = oss2.AuthV4 if settings.storage_region else oss2.Auth
                auth = auth_class(access_key, secret_key)
            self.bucket = oss2.Bucket(
                auth, settings.storage_endpoint, bucket,
                is_cname=getattr(settings, "storage_oss_is_cname", False),
                connect_timeout=settings.storage_timeout_seconds,
                region=settings.storage_region or None,
            )
        except Exception:
            raise _configuration_error() from None

    def _key(self, key: str) -> str:
        _validate_key(key)
        return key

    def put(self, key: str, data: bytes, content_type: str) -> None:
        object_key = self._key(key)
        try:
            self.bucket.put_object(object_key, data, headers={"Content-Type": content_type})
        except Exception:
            raise _unavailable() from None

    def get(self, key: str) -> bytes:
        object_key = self._key(key)
        try:
            response = self.bucket.get_object(object_key)
            try:
                return response.read()
            finally:
                response.close()
        except Exception as error:
            if getattr(error, "code", None) == "NoSuchKey":
                raise _not_found() from None
            raise _unavailable() from None

    def delete(self, key: str) -> None:
        object_key = self._key(key)
        try:
            self.bucket.delete_object(object_key)
        except Exception:
            raise _unavailable() from None

    def check(self) -> None:
        try:
            self.bucket.get_bucket_info()
        except Exception:
            raise _unavailable() from None


def build_storage(settings: Settings) -> ObjectStorage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_local_root)
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    if settings.storage_backend == "oss":
        return OSSStorage(settings)
    raise _configuration_error()
