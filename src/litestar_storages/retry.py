"""Retry utilities with exponential backoff for storage operations."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import ParamSpec, TypeVar

from litestar_storages.exceptions import StorageConnectionError, StorageError

__all__ = ("RetryConfig", "retry", "with_retry")

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts (0 = no retries)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        retryable_exceptions: Exception types that should trigger a retry
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: (StorageConnectionError, TimeoutError, ConnectionError)
    )

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number.

        Uses exponential backoff with optional jitter.

        Args:
            attempt: The attempt number (0-indexed)

        Returns:
            Delay in seconds before the next retry
        """
        delay = min(
            self.base_delay * (self.exponential_base**attempt),
            self.max_delay,
        )

        if self.jitter:
            # Add up to 25% jitter
            delay = delay * (0.75 + random.random() * 0.5)  # noqa: S311

        return delay


def retry(
    config: RetryConfig | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator for adding retry logic to async functions.

    Args:
        config: Retry configuration. If None, uses default RetryConfig.

    Returns:
        Decorator function

    Example::

        @retry(RetryConfig(max_retries=5))
        async def upload_file(key: str, data: bytes) -> None:
            await storage.put(key, data)
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        func_name = getattr(func, "__name__", repr(func))

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:  # noqa: PERF203
                    last_exception = e

                    if attempt < config.max_retries:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            "Retry attempt %d/%d for %s after %.2fs: %s",
                            attempt + 1,
                            config.max_retries,
                            func_name,
                            delay,
                            str(e),
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.exception(
                            "All %d retries exhausted for %s",
                            config.max_retries,
                            func_name,
                        )
                except Exception:
                    # Non-retryable exception, re-raise immediately
                    raise

            # Should not reach here, but satisfy type checker
            if last_exception:
                raise last_exception
            raise StorageError("Unexpected retry failure")

        return wrapper

    return decorator


async def with_retry(
    func: Callable[[], Awaitable[T]],
    config: RetryConfig | None = None,
) -> T:
    """Execute an async function with retry logic.

    This is a functional alternative to the @retry decorator for cases
    where you need to retry a specific operation inline.

    Args:
        func: Async callable to execute
        config: Retry configuration. If None, uses default RetryConfig.

    Returns:
        Result of the function call

    Raises:
        StorageError: If all retries are exhausted

    Example::

        result = await with_retry(lambda: storage.put("key", data), RetryConfig(max_retries=5))
    """
    if config is None:
        config = RetryConfig()

    last_exception: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func()
        except config.retryable_exceptions as e:  # noqa: PERF203
            last_exception = e

            if attempt < config.max_retries:
                delay = config.calculate_delay(attempt)
                logger.warning(
                    "Retry attempt %d/%d after %.2fs: %s",
                    attempt + 1,
                    config.max_retries,
                    delay,
                    str(e),
                )
                await asyncio.sleep(delay)
            else:
                logger.exception(
                    "All %d retries exhausted",
                    config.max_retries,
                )
        except Exception:
            # Non-retryable exception, re-raise immediately
            raise

    if last_exception:
        raise last_exception
    raise StorageError("Unexpected retry failure")
