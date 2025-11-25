"""Tests for retry utilities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from litestar_storages.exceptions import StorageConnectionError
from litestar_storages.retry import RetryConfig, retry, with_retry


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert StorageConnectionError in config.retryable_exceptions

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False,
        )

        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.jitter is False

    def test_calculate_delay_exponential(self) -> None:
        """Test exponential delay calculation without jitter."""
        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            jitter=False,
        )

        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 8.0

    def test_calculate_delay_max_cap(self) -> None:
        """Test delay is capped at max_delay."""
        config = RetryConfig(
            base_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False,
        )

        assert config.calculate_delay(10) == 5.0

    def test_calculate_delay_with_jitter(self) -> None:
        """Test delay with jitter is within expected range."""
        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            jitter=True,
        )

        # With jitter, delay should be between 75% and 125% of base
        for _ in range(10):
            delay = config.calculate_delay(0)
            assert 0.75 <= delay <= 1.25


class TestRetryDecorator:
    """Tests for @retry decorator."""

    async def test_success_no_retry(self) -> None:
        """Test successful call doesn't retry."""
        call_count = 0

        @retry(RetryConfig(max_retries=3))
        async def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()

        assert result == "success"
        assert call_count == 1

    async def test_retry_on_connection_error(self) -> None:
        """Test retry on connection error."""
        call_count = 0

        @retry(RetryConfig(max_retries=3, base_delay=0.01, jitter=False))
        async def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise StorageConnectionError("Connection failed")
            return "success"

        result = await flaky_func()

        assert result == "success"
        assert call_count == 3

    async def test_max_retries_exhausted(self) -> None:
        """Test exception raised after max retries."""
        call_count = 0

        @retry(RetryConfig(max_retries=2, base_delay=0.01, jitter=False))
        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise StorageConnectionError("Always fails")

        with pytest.raises(StorageConnectionError):
            await always_fail()

        assert call_count == 3  # Initial + 2 retries

    async def test_non_retryable_exception(self) -> None:
        """Test non-retryable exception is raised immediately."""
        call_count = 0

        @retry(RetryConfig(max_retries=3, base_delay=0.01))
        async def raise_value_error() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError, match="Not retryable"):
            await raise_value_error()

        assert call_count == 1  # No retries for non-retryable exceptions

    async def test_custom_retryable_exceptions(self) -> None:
        """Test custom retryable exceptions."""
        call_count = 0

        @retry(
            RetryConfig(
                max_retries=2,
                base_delay=0.01,
                jitter=False,
                retryable_exceptions=(ValueError,),
            )
        )
        async def raise_value_error() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retryable now")
            return "success"

        result = await raise_value_error()

        assert result == "success"
        assert call_count == 2


class TestWithRetry:
    """Tests for with_retry function."""

    async def test_success(self) -> None:
        """Test successful execution."""
        mock_func = AsyncMock(return_value="success")

        result = await with_retry(mock_func)

        assert result == "success"
        mock_func.assert_called_once()

    async def test_retry_then_success(self) -> None:
        """Test retry then success."""
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise StorageConnectionError("Temporary failure")
            return "success"

        config = RetryConfig(max_retries=3, base_delay=0.01, jitter=False)
        result = await with_retry(flaky, config)

        assert result == "success"
        assert call_count == 2

    async def test_all_retries_fail(self) -> None:
        """Test all retries exhausted."""

        async def always_fail() -> str:
            raise StorageConnectionError("Always fails")

        config = RetryConfig(max_retries=2, base_delay=0.01, jitter=False)

        with pytest.raises(StorageConnectionError):
            await with_retry(always_fail, config)

    async def test_with_lambda(self) -> None:
        """Test with lambda function."""
        storage_mock = MagicMock()
        storage_mock.put = AsyncMock(return_value="stored")

        config = RetryConfig(max_retries=1, base_delay=0.01)
        result = await with_retry(lambda: storage_mock.put("key", b"data"), config)

        assert result == "stored"
        storage_mock.put.assert_called_once_with("key", b"data")
