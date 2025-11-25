"""Shared pytest fixtures for litestar-storages tests."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from litestar_storages import Storage
    from litestar_storages.backends.azure import AzureStorage
    from litestar_storages.backends.filesystem import FileSystemStorage
    from litestar_storages.backends.gcs import GCSStorage
    from litestar_storages.backends.memory import MemoryStorage
    from litestar_storages.backends.s3 import S3Storage


# ==================================================================================== #
# PYTEST CONFIGURATION
# ==================================================================================== #


def pytest_configure(config):
    """Configure pytest with custom settings and markers."""
    # Register custom markers
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Tests that take more than 1 second")
    config.addinivalue_line("markers", "requires_network: Tests requiring network access")

    # Set environment variables for test optimization
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def pytest_runtest_setup(item):
    """Setup for each test - configure socket blocking for unit tests."""
    # Allow network access for integration tests and tests marked with requires_network
    markers = [mark.name for mark in item.iter_markers()]
    if "integration" not in markers and "requires_network" not in markers:
        # Socket blocking is automatically enabled by pytest-socket for unit tests
        # unless explicitly allowed via --allow-hosts
        pass


# Async test configuration
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# MemoryStorage fixtures
@pytest.fixture
def memory_storage() -> MemoryStorage:
    """
    Fresh memory storage instance for each test.

    Provides isolated in-memory storage with no size limits.
    Ideal for fast unit tests that don't require persistence.
    """
    from litestar_storages.backends.memory import MemoryConfig, MemoryStorage

    return MemoryStorage(config=MemoryConfig())


@pytest.fixture
def memory_storage_with_limit() -> MemoryStorage:
    """
    Memory storage with size limit for testing capacity constraints.

    Limited to 1MB total storage to test max_size enforcement.
    """
    from litestar_storages.backends.memory import MemoryConfig, MemoryStorage

    return MemoryStorage(config=MemoryConfig(max_size=1024 * 1024))  # 1MB


# FileSystemStorage fixtures
@pytest.fixture
def filesystem_storage(tmp_path: Path) -> FileSystemStorage:
    """
    Filesystem storage in temporary directory.

    Uses pytest's tmp_path fixture to provide clean isolated filesystem
    for each test. Directory is automatically cleaned up after test.

    Args:
        tmp_path: pytest fixture providing temporary directory path
    """
    from litestar_storages.backends.filesystem import FileSystemConfig, FileSystemStorage

    return FileSystemStorage(
        config=FileSystemConfig(
            path=tmp_path,
            create_dirs=True,
            permissions=0o644,
        )
    )


@pytest.fixture
def filesystem_storage_with_base_url(tmp_path: Path) -> FileSystemStorage:
    """
    Filesystem storage with base URL configured for URL generation.

    Tests URL generation features when base_url is configured.
    """
    from litestar_storages.backends.filesystem import FileSystemConfig, FileSystemStorage

    return FileSystemStorage(
        config=FileSystemConfig(
            path=tmp_path,
            base_url="https://cdn.example.com/uploads",
            create_dirs=True,
        )
    )


# S3Storage fixtures
# NOTE: Uses moto server mode for aiobotocore compatibility.
# The decorator-based mock_aws() doesn't work with aiobotocore's async API.


@pytest.fixture
def moto_server():
    """
    Start moto server for S3 mocking with aiobotocore.

    Uses moto's ThreadedMotoServer to run moto in a separate thread,
    which properly handles aiobotocore's async requests.
    """
    from moto.server import ThreadedMotoServer

    # Start moto server on a free port
    server = ThreadedMotoServer(port="0", verbose=False)
    server.start()

    # Get the actual port assigned
    host, port = server.get_host_and_port()
    endpoint_url = f"http://{host}:{port}"

    # Set fake AWS credentials for moto
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    yield endpoint_url

    server.stop()


@pytest.fixture
def mock_s3_bucket(moto_server: str):
    """
    Create mock S3 bucket using moto server.

    Creates the bucket before the test and cleans all objects after.

    Args:
        moto_server: Endpoint URL from moto server fixture
    """
    import boto3

    # Create sync client to set up bucket
    s3_client = boto3.client(
        "s3",
        endpoint_url=moto_server,
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    s3_client.create_bucket(Bucket="test-bucket")

    yield {"client": s3_client, "endpoint_url": moto_server}

    # Cleanup: delete all objects in the bucket after test
    try:
        response = s3_client.list_objects_v2(Bucket="test-bucket")
        if "Contents" in response:
            for obj in response["Contents"]:
                s3_client.delete_object(Bucket="test-bucket", Key=obj["Key"])
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def s3_storage(mock_s3_bucket: dict) -> S3Storage:
    """
    S3 storage instance with mocked AWS backend.

    Uses moto server to mock AWS S3 service for testing without real AWS credentials.
    All operations are local and fast.

    Args:
        mock_s3_bucket: Fixture providing mocked S3 client with test bucket
    """
    from datetime import timedelta

    from litestar_storages.backends.s3 import S3Config, S3Storage

    return S3Storage(
        config=S3Config(
            bucket="test-bucket",
            region="us-east-1",
            endpoint_url=mock_s3_bucket["endpoint_url"],
            access_key_id="testing",
            secret_access_key="testing",
            presigned_expiry=timedelta(hours=1),
        )
    )


@pytest.fixture
def s3_storage_with_prefix(mock_s3_bucket: dict) -> S3Storage:
    """
    S3 storage with key prefix for namespace isolation.

    Tests prefix handling where all keys are automatically prefixed.
    Useful for multi-tenant scenarios or organizing storage by environment.
    """
    from datetime import timedelta

    from litestar_storages.backends.s3 import S3Config, S3Storage

    return S3Storage(
        config=S3Config(
            bucket="test-bucket",
            region="us-east-1",
            endpoint_url=mock_s3_bucket["endpoint_url"],
            access_key_id="testing",
            secret_access_key="testing",
            prefix="test-prefix/",
            presigned_expiry=timedelta(hours=1),
        )
    )


@pytest.fixture
def s3_storage_custom_endpoint(mock_s3_bucket: dict) -> S3Storage:
    """
    S3 storage with custom endpoint for S3-compatible services.

    Tests endpoint_url configuration for services like Cloudflare R2,
    DigitalOcean Spaces, MinIO, etc.
    """
    from datetime import timedelta

    from litestar_storages.backends.s3 import S3Config, S3Storage

    return S3Storage(
        config=S3Config(
            bucket="test-bucket",
            region="us-east-1",
            endpoint_url=mock_s3_bucket["endpoint_url"],
            access_key_id="testing",
            secret_access_key="testing",
            presigned_expiry=timedelta(hours=1),
        )
    )


# GCSStorage fixtures
# NOTE: Uses fake-gcs-server emulator for testing.
# Start the emulator with: docker run -d -p 4443:4443 fsouza/fake-gcs-server


@pytest.fixture
def gcs_server():
    """
    GCS emulator endpoint for testing.

    Uses fake-gcs-server running on localhost:4443.
    Start the emulator with:
        docker run -d -p 4443:4443 fsouza/fake-gcs-server -scheme http

    If the emulator is not running, tests using this fixture will be skipped.
    """
    import socket

    # Check if fake-gcs-server is running
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex(("localhost", 4443))
        if result != 0:
            pytest.skip(
                "GCS emulator not running. Start with: docker run -d -p 4443:4443 fsouza/fake-gcs-server -scheme http"
            )
    finally:
        sock.close()

    return "http://localhost:4443"


@pytest.fixture
def mock_gcs_bucket(gcs_server: str):
    """
    Create mock GCS bucket using fake-gcs-server.

    Creates the bucket before the test and cleans all objects after.
    """
    import requests

    # Create bucket via fake-gcs-server API
    bucket_url = f"{gcs_server}/storage/v1/b"
    requests.post(
        bucket_url,
        params={"project": "test-project"},
        json={"name": "test-bucket"},
        timeout=5,
    )

    yield {"endpoint_url": gcs_server, "bucket": "test-bucket"}

    # Cleanup: delete all objects in the bucket after test
    try:
        objects_url = f"{gcs_server}/storage/v1/b/test-bucket/o"
        response = requests.get(objects_url, timeout=5)
        if response.ok:
            data = response.json()
            for item in data.get("items", []):
                object_url = f"{gcs_server}/storage/v1/b/test-bucket/o/{item['name']}"
                requests.delete(object_url, timeout=5)
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
async def gcs_storage(mock_gcs_bucket: dict) -> GCSStorage:
    """
    GCS storage instance with fake-gcs-server backend.

    Uses fake-gcs-server to mock GCS for testing without real GCP credentials.
    All operations are local and fast.
    """
    from datetime import timedelta

    from litestar_storages.backends.gcs import GCSConfig, GCSStorage

    storage = GCSStorage(
        config=GCSConfig(
            bucket=mock_gcs_bucket["bucket"],
            project="test-project",
            api_root=mock_gcs_bucket["endpoint_url"],
            presigned_expiry=timedelta(hours=1),
        )
    )

    yield storage

    # Cleanup
    await storage.close()


@pytest.fixture
def gcs_storage_with_prefix(mock_gcs_bucket: dict) -> GCSStorage:
    """
    GCS storage with key prefix for namespace isolation.
    """
    from datetime import timedelta

    from litestar_storages.backends.gcs import GCSConfig, GCSStorage

    return GCSStorage(
        config=GCSConfig(
            bucket=mock_gcs_bucket["bucket"],
            project="test-project",
            api_root=mock_gcs_bucket["endpoint_url"],
            prefix="test-prefix/",
            presigned_expiry=timedelta(hours=1),
        )
    )


# AzureStorage fixtures
# NOTE: Uses Azurite emulator for testing.
# Start the emulator with:
#   docker run -d -p 10000:10000 mcr.microsoft.com/azure-storage/azurite azurite-blob --blobHost 0.0.0.0

# Azurite well-known credentials
AZURITE_ACCOUNT_NAME = "devstoreaccount1"
AZURITE_ACCOUNT_KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="


@pytest.fixture
def azurite_server():
    """
    Azurite emulator endpoint for testing.

    Uses Azurite running on localhost:10000.
    Start the emulator with:
        docker run -d -p 10000:10000 mcr.microsoft.com/azure-storage/azurite azurite-blob --blobHost 0.0.0.0

    If the emulator is not running, tests using this fixture will be skipped.
    """
    import socket

    # Check if Azurite is running
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex(("localhost", 10000))
        if result != 0:
            pytest.skip(
                "Azurite emulator not running. Start with: "
                "docker run -d -p 10000:10000 mcr.microsoft.com/azure-storage/azurite azurite-blob --blobHost 0.0.0.0"
            )
    finally:
        sock.close()

    return (
        f"DefaultEndpointsProtocol=http;"
        f"AccountName={AZURITE_ACCOUNT_NAME};"
        f"AccountKey={AZURITE_ACCOUNT_KEY};"
        f"BlobEndpoint=http://127.0.0.1:10000/{AZURITE_ACCOUNT_NAME};"
    )


@pytest.fixture
def mock_azure_container(azurite_server: str):
    """
    Create mock Azure container using Azurite.

    Creates the container before the test and cleans all blobs after.
    """
    from azure.storage.blob import ContainerClient

    container_name = "test-container"

    # Create container using sync client
    container_client = ContainerClient.from_connection_string(
        conn_str=azurite_server,
        container_name=container_name,
    )

    try:
        container_client.create_container()
    except Exception:
        pass  # Container may already exist

    yield {"connection_string": azurite_server, "container": container_name}

    # Cleanup: delete all blobs in the container after test
    try:
        for blob in container_client.list_blobs():
            container_client.delete_blob(blob.name)
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
async def azure_storage(mock_azure_container: dict) -> AsyncGenerator[AzureStorage, None]:
    """
    Azure storage instance with Azurite backend.

    Uses Azurite to mock Azure Blob Storage for testing without real Azure credentials.
    All operations are local and fast.
    """
    from datetime import timedelta

    from litestar_storages.backends.azure import AzureConfig, AzureStorage

    storage = AzureStorage(
        config=AzureConfig(
            container=mock_azure_container["container"],
            connection_string=mock_azure_container["connection_string"],
            presigned_expiry=timedelta(hours=1),
        )
    )

    yield storage

    # Cleanup
    await storage.close()


@pytest.fixture
def azure_storage_with_prefix(mock_azure_container: dict) -> AzureStorage:
    """
    Azure storage with key prefix for namespace isolation.
    """
    from datetime import timedelta

    from litestar_storages.backends.azure import AzureConfig, AzureStorage

    return AzureStorage(
        config=AzureConfig(
            container=mock_azure_container["container"],
            connection_string=mock_azure_container["connection_string"],
            prefix="test-prefix/",
            presigned_expiry=timedelta(hours=1),
        )
    )


# Parametrized fixture for protocol compliance tests
# NOTE: S3 is excluded from default parametrization because it requires
# the moto server fixture which adds overhead. S3 tests are run separately
# via the integration marker.
@pytest.fixture(params=["memory", "filesystem"])
async def any_storage(
    request: pytest.FixtureRequest,
    memory_storage: MemoryStorage,
    filesystem_storage: FileSystemStorage,
) -> AsyncGenerator[Storage, None]:
    """
    Parametrized fixture that yields each storage backend.

    Tests using this fixture will run against memory and filesystem backends
    to ensure protocol compliance across different storage implementations.

    This is the key fixture for verifying that all backends implement
    the Storage protocol correctly and consistently.

    Args:
        request: pytest fixture request object with param
        memory_storage: MemoryStorage instance
        filesystem_storage: FileSystemStorage instance

    Yields:
        Storage instance (one backend per test run)
    """
    storage_map = {
        "memory": memory_storage,
        "filesystem": filesystem_storage,
    }

    storage = storage_map[request.param]
    yield storage

    # Cleanup: clear all data after test
    import contextlib

    with contextlib.suppress(Exception):
        # Try to clean up all files
        async for file in storage.list():
            with contextlib.suppress(Exception):
                await storage.delete(file.key)


# Test data fixtures - use session scope for immutable test data
@pytest.fixture(scope="session")
def sample_text_data() -> bytes:
    """Sample text data for testing file operations.

    Session-scoped as this is immutable data that can be reused across all tests.
    """
    return b"Hello, World! This is test data."


@pytest.fixture(scope="session")
def sample_binary_data() -> bytes:
    """Sample binary data for testing file operations.

    Session-scoped as this is immutable data that can be reused across all tests.
    """
    return bytes(range(256))


@pytest.fixture(scope="session")
def large_data() -> bytes:
    """Large data for testing chunked operations and streaming.

    Session-scoped to avoid recreating 1MB of data for each test.
    """
    return b"x" * 1024 * 1024  # 1MB of data


@pytest.fixture
def sample_metadata() -> dict[str, str]:
    """Sample metadata for testing metadata storage.

    Function-scoped as tests may modify this dict.
    """
    return {
        "author": "test-user",
        "environment": "test",
        "purpose": "unit-test",
    }


# Async iterator fixture
@pytest.fixture
def async_data_chunks():
    """
    Factory fixture for creating async data iterators.

    Returns a callable that creates async iterators from bytes,
    useful for testing streaming upload functionality.
    """

    async def _create_async_chunks(data: bytes, chunk_size: int = 1024):
        """Split data into chunks and yield asynchronously."""
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

    return _create_async_chunks


# Litestar test fixtures
@pytest.fixture
def litestar_app():
    """
    Basic Litestar application for plugin integration tests.

    Creates a minimal Litestar app instance for testing
    plugin registration and dependency injection.

    Function-scoped to ensure each test has a clean app instance.
    """
    from litestar import Litestar

    return Litestar(route_handlers=[])


@pytest.fixture
async def litestar_test_client(litestar_app):
    """
    Async test client for Litestar application.

    Provides an async HTTP client for testing Litestar endpoints
    with storage integration.
    """
    from litestar.testing import AsyncTestClient

    async with AsyncTestClient(app=litestar_app) as client:
        yield client


# Pytest-asyncio configuration
pytest_plugins = ("pytest_asyncio",)


# ==================================================================================== #
# PYTEST-XDIST OPTIMIZATION
# ==================================================================================== #


@pytest.fixture(scope="session")
def worker_id(request):
    """Get the worker ID for pytest-xdist.

    Returns 'master' if not running with xdist, otherwise returns the worker ID.
    Useful for creating worker-specific resources.
    """
    if hasattr(request.config, "workerinput"):
        return request.config.workerinput["workerid"]
    return "master"
