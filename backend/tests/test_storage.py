"""Storage contract tests run entirely offline, including both cloud SDKs."""

import io
import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import SecretStr

from app.utils.document_errors import DocumentError
from app.utils.storage import LocalStorage, OSSStorage, S3Storage, build_storage


def settings(tmp_path, **overrides):
    values = dict(
        storage_backend="local",
        storage_local_root=tmp_path / "objects",
        storage_bucket="private-documents",
        storage_region="ap-southeast-2",
        storage_endpoint="",
        storage_prefix="c5",
        storage_access_key_id=SecretStr(""),
        storage_access_key_secret=SecretStr(""),
        storage_session_token=SecretStr(""),
        storage_timeout_seconds=7,
        storage_oss_is_cname=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def s3_sdk(monkeypatch):
    client = Mock()
    sdk = SimpleNamespace(client=Mock(return_value=client))
    config = Mock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setitem(sys.modules, "boto3", sdk)
    monkeypatch.setitem(sys.modules, "botocore.config", SimpleNamespace(Config=config))
    return SimpleNamespace(sdk=sdk, client=client, config=config)


@pytest.fixture
def oss_sdk(monkeypatch):
    bucket = Mock()
    sdk = SimpleNamespace(
        Bucket=Mock(return_value=bucket), Auth=Mock(), AuthV4=Mock(), StsAuth=Mock()
    )
    monkeypatch.setitem(sys.modules, "oss2", sdk)
    return SimpleNamespace(sdk=sdk, bucket=bucket)


def oss_settings(tmp_path, **overrides):
    values = dict(
        storage_backend="oss", storage_endpoint="https://oss-ap-southeast-1.aliyuncs.com",
        storage_region="ap-southeast-1", storage_access_key_id=SecretStr("test-key"),
        storage_access_key_secret=SecretStr("test-secret"),
    )
    values.update(overrides)
    return settings(tmp_path, **values)


def assert_error(error, code, status):
    assert error.value.code == code
    assert error.value.status_code == status
    assert "secret" not in str(error.value)


def test_local_lifecycle_and_private_files(tmp_path):
    store = LocalStorage(tmp_path / "objects")
    store.put("session/file.pdf", b"first version", "application/pdf")
    assert store.get("session/file.pdf") == b"first version"
    assert (store.root / "session/file.pdf").stat().st_mode & 0o777 == 0o600
    store.put("session/file.pdf", b"second version", "application/pdf")
    assert store.get("session/file.pdf") == b"second version"
    store.delete("session/file.pdf")
    store.delete("session/file.pdf")
    with pytest.raises(DocumentError) as error:
        store.get("session/file.pdf")
    assert_error(error, "FILE_NOT_FOUND", 404)


def test_local_check_cleans_its_probe_and_preserves_documents(tmp_path):
    store = LocalStorage(tmp_path)
    store.put("existing.pdf", b"keep", "application/pdf")
    store.check()
    assert list(tmp_path.iterdir()) == [tmp_path / "existing.pdf"]
    assert store.get("existing.pdf") == b"keep"


def test_local_failed_atomic_replace_keeps_existing_file(tmp_path, monkeypatch):
    store = LocalStorage(tmp_path)
    store.put("existing.pdf", b"keep", "application/pdf")
    monkeypatch.setattr(os, "replace", Mock(side_effect=OSError("secret backend detail")))
    with pytest.raises(DocumentError) as error:
        store.put("existing.pdf", b"incomplete replacement", "application/pdf")
    assert_error(error, "STORAGE_UNAVAILABLE", 503)
    assert store.get("existing.pdf") == b"keep"
    assert list(tmp_path.iterdir()) == [tmp_path / "existing.pdf"]


@pytest.mark.parametrize("operation", ["put", "get", "delete"])
@pytest.mark.parametrize("kind", ["directory", "file"])
def test_local_symlinks_cannot_escape_root(tmp_path, operation, kind):
    root = tmp_path / "objects"
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "protected.pdf"
    target.write_bytes(b"protected")
    store = LocalStorage(root)
    link = root / "link"
    link.symlink_to(outside if kind == "directory" else target)
    key = "link/protected.pdf" if kind == "directory" else "link"
    with pytest.raises(DocumentError) as error:
        if operation == "put":
            store.put(key, b"overwrite", "application/pdf")
        else:
            getattr(store, operation)(key)
    assert_error(error, "STORAGE_UNAVAILABLE", 503)
    assert target.read_bytes() == b"protected"
    assert link.is_symlink()


@pytest.mark.parametrize("backend", ["local", "s3", "oss"])
@pytest.mark.parametrize("key", ["", "/absolute", "../escape", "a/../b", "./x", "a//b", "a/", "a\\b", "a\x00b"])
def test_every_adapter_rejects_unsafe_keys(tmp_path, s3_sdk, oss_sdk, backend, key):
    store = {
        "local": lambda: LocalStorage(tmp_path),
        "s3": lambda: S3Storage(settings(tmp_path)),
        "oss": lambda: OSSStorage(oss_settings(tmp_path)),
    }[backend]()
    for operation in (lambda: store.put(key, b"data", "application/pdf"),
                      lambda: store.get(key), lambda: store.delete(key)):
        with pytest.raises(DocumentError) as error:
            operation()
        assert_error(error, "STORAGE_CONFIGURATION_ERROR", 503)
    assert not s3_sdk.client.mock_calls
    assert not oss_sdk.bucket.mock_calls


def test_s3_lifecycle_default_credentials_private_requests_and_readiness(tmp_path, s3_sdk):
    store = S3Storage(settings(tmp_path))
    options = s3_sdk.sdk.client.call_args.kwargs
    assert options["region_name"] == "ap-southeast-2"
    assert not any(key.startswith("aws_") for key in options)
    s3_sdk.config.assert_called_once_with(
        connect_timeout=7, read_timeout=7,
        retries={"mode": "standard", "total_max_attempts": 3},
    )
    store.put("session/file.pdf", b"pdf", "application/pdf")
    s3_sdk.client.put_object.assert_called_once_with(
        Bucket="private-documents", Key="session/file.pdf", Body=b"pdf", ContentType="application/pdf"
    )
    body = io.BytesIO(b"pdf")
    s3_sdk.client.get_object.return_value = {"Body": body}
    assert store.get("session/file.pdf") == b"pdf"
    assert body.closed
    s3_sdk.client.get_object.assert_called_once_with(Bucket="private-documents", Key="session/file.pdf")
    store.delete("session/file.pdf")
    s3_sdk.client.delete_object.assert_called_once_with(Bucket="private-documents", Key="session/file.pdf")
    s3_sdk.client.reset_mock()
    store.check()
    assert s3_sdk.client.mock_calls == [(("head_bucket"), (), {"Bucket": "private-documents"})]


def test_s3_explicit_credentials_session_token_and_custom_endpoint(tmp_path, s3_sdk):
    S3Storage(settings(
        tmp_path, storage_endpoint="http://127.0.0.1:9000",
        storage_access_key_id=SecretStr("test-key"),
        storage_access_key_secret=SecretStr("test-secret"),
        storage_session_token=SecretStr("test-token"),
    ))
    options = s3_sdk.sdk.client.call_args.kwargs
    assert options["endpoint_url"] == "http://127.0.0.1:9000"
    assert options["aws_access_key_id"] == "test-key"
    assert options["aws_secret_access_key"] == "test-secret"
    assert options["aws_session_token"] == "test-token"


@pytest.mark.parametrize("code,expected", [("NoSuchKey", "FILE_NOT_FOUND"), ("NoSuchBucket", "STORAGE_UNAVAILABLE"), ("AccessDenied", "STORAGE_UNAVAILABLE")])
def test_s3_missing_object_is_distinct_from_provider_failure(tmp_path, s3_sdk, code, expected):
    failure = RuntimeError("secret backend detail")
    failure.response = {"Error": {"Code": code}}
    s3_sdk.client.get_object.side_effect = failure
    with pytest.raises(DocumentError) as error:
        S3Storage(settings(tmp_path)).get("file.pdf")
    assert_error(error, expected, 404 if expected == "FILE_NOT_FOUND" else 503)


@pytest.mark.parametrize("operation,method", [("put", "put_object"), ("delete", "delete_object"), ("check", "head_bucket")])
def test_s3_failures_do_not_leak_provider_details(tmp_path, s3_sdk, operation, method):
    getattr(s3_sdk.client, method).side_effect = RuntimeError("secret backend detail")
    store = S3Storage(settings(tmp_path))
    with pytest.raises(DocumentError) as error:
        if operation == "put":
            store.put("file.pdf", b"pdf", "application/pdf")
        elif operation == "check":
            store.check()
        else:
            store.delete("file.pdf")
    assert_error(error, "STORAGE_UNAVAILABLE", 503)


def test_oss_lifecycle_v4_private_requests_and_readiness(tmp_path, oss_sdk):
    store = OSSStorage(oss_settings(tmp_path))
    oss_sdk.sdk.AuthV4.assert_called_once_with("test-key", "test-secret")
    oss_sdk.sdk.Bucket.assert_called_once_with(
        oss_sdk.sdk.AuthV4.return_value, "https://oss-ap-southeast-1.aliyuncs.com", "private-documents",
        connect_timeout=7, region="ap-southeast-1", is_cname=False,
    )
    store.put("file.pdf", b"pdf", "application/pdf")
    oss_sdk.bucket.put_object.assert_called_once_with("file.pdf", b"pdf", headers={"Content-Type": "application/pdf"})
    body = io.BytesIO(b"pdf")
    oss_sdk.bucket.get_object.return_value = body
    assert store.get("file.pdf") == b"pdf"
    assert body.closed
    oss_sdk.bucket.get_object.assert_called_once_with("file.pdf")
    store.delete("file.pdf")
    oss_sdk.bucket.delete_object.assert_called_once_with("file.pdf")
    oss_sdk.bucket.reset_mock()
    store.check()
    assert oss_sdk.bucket.mock_calls == [(("get_bucket_info"), (), {})]


def test_oss_sts_and_cname_settings(tmp_path, oss_sdk):
    OSSStorage(oss_settings(tmp_path, storage_session_token=SecretStr("test-token"), storage_oss_is_cname=True))
    oss_sdk.sdk.StsAuth.assert_called_once_with("test-key", "test-secret", "test-token", auth_version="v4")
    assert oss_sdk.sdk.Bucket.call_args.kwargs["is_cname"] is True


def test_oss_v1_fallback_without_region(tmp_path, oss_sdk):
    OSSStorage(oss_settings(tmp_path, storage_region=""))
    oss_sdk.sdk.Auth.assert_called_once_with("test-key", "test-secret")
    assert oss_sdk.sdk.Bucket.call_args.kwargs["region"] is None


@pytest.mark.parametrize("code,expected", [("NoSuchKey", "FILE_NOT_FOUND"), ("NoSuchBucket", "STORAGE_UNAVAILABLE"), ("AccessDenied", "STORAGE_UNAVAILABLE")])
def test_oss_missing_object_is_distinct_from_provider_failure(tmp_path, oss_sdk, code, expected):
    failure = RuntimeError("secret backend detail")
    failure.code = code
    oss_sdk.bucket.get_object.side_effect = failure
    with pytest.raises(DocumentError) as error:
        OSSStorage(oss_settings(tmp_path)).get("file.pdf")
    assert_error(error, expected, 404 if expected == "FILE_NOT_FOUND" else 503)


@pytest.mark.parametrize("operation,method", [("put", "put_object"), ("delete", "delete_object"), ("check", "get_bucket_info")])
def test_oss_failures_do_not_leak_provider_details(tmp_path, oss_sdk, operation, method):
    getattr(oss_sdk.bucket, method).side_effect = RuntimeError("secret backend detail")
    store = OSSStorage(oss_settings(tmp_path))
    with pytest.raises(DocumentError) as error:
        if operation == "put":
            store.put("file.pdf", b"pdf", "application/pdf")
        elif operation == "check":
            store.check()
        else:
            store.delete("file.pdf")
    assert_error(error, "STORAGE_UNAVAILABLE", 503)


@pytest.mark.parametrize("backend,expected", [("local", LocalStorage), ("s3", S3Storage), ("oss", OSSStorage)])
def test_factory_selects_requested_backend(tmp_path, s3_sdk, oss_sdk, backend, expected):
    config = oss_settings(tmp_path) if backend == "oss" else settings(tmp_path, storage_backend=backend)
    assert isinstance(build_storage(config), expected)


@pytest.mark.parametrize("backend,sdk_name", [(S3Storage, "boto3"), (OSSStorage, "oss2")])
def test_missing_cloud_sdk_does_not_break_local_storage(tmp_path, monkeypatch, backend, sdk_name):
    monkeypatch.setitem(sys.modules, sdk_name, None)
    local = build_storage(settings(tmp_path))
    local.check()
    with pytest.raises(DocumentError) as error:
        backend(oss_settings(tmp_path))
    assert_error(error, "STORAGE_CONFIGURATION_ERROR", 503)


@pytest.mark.parametrize("backend,overrides", [
    (S3Storage, {"storage_bucket": ""}),
    (S3Storage, {"storage_access_key_id": SecretStr("incomplete")}),
    (S3Storage, {"storage_session_token": SecretStr("orphan-token")}),
    (OSSStorage, {"storage_bucket": ""}),
    (OSSStorage, {"storage_endpoint": ""}),
    (OSSStorage, {"storage_access_key_secret": SecretStr("")}),
])
def test_bad_configuration_fails_before_sdk_access(tmp_path, s3_sdk, oss_sdk, backend, overrides):
    config = oss_settings(tmp_path, **overrides) if backend is OSSStorage else settings(tmp_path, **overrides)
    with pytest.raises(DocumentError) as error:
        backend(config)
    assert_error(error, "STORAGE_CONFIGURATION_ERROR", 503)
    s3_sdk.sdk.client.assert_not_called()
    oss_sdk.sdk.Bucket.assert_not_called()
