"""
Dataverse metadata propagation retry helpers (self-contained copy for framework_power).

Dataverse needs time to propagate table/column/relationship metadata after each
create (index build, cache propagation). This module provides retry decorators and
wait helpers to absorb those delays. The default error patterns are expanded with
the transient signals documented by the Dataverse `dv-metadata` skill.

This is a standalone copy managed inside `framework_power/`; it does NOT import
from the legacy `framework/` package.
"""

import time
import logging
import random
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class MetadataPropagationError(Exception):
    """Raised when metadata does not become available within the timeout."""


# Transient error signals that justify a retry (Dataverse metadata cache / lock contention).
# NOTE: "already exists" / 0x80040237 is intentionally NOT here - it is a terminal
# "skip" condition handled by the deployer, not a retryable delay.
DEFAULT_RETRY_PATTERNS: list[str] = [
    "not found",
    "cannot be found",
    "does not exist",
    "entity not found",
    "attribute not found",
    "could not be found",
    "invalid entity",
    "invalid attribute",
    "404",
    "metadata id",
    "depends on",
    # dv-metadata skill transient signals:
    "another",                  # "another customization operation is running"
    "running",                  # lock contention
    "customization operation",  # lock contention
    "metadatacache",            # "EntityId not found in MetadataCache"
    "0x80040216",               # transient metadata cache error
    "0x80060891",               # metadata cache not ready after table create
]


def retry_on_metadata_error(
    max_retries: int = 5,
    initial_delay: float = 2.0,
    backoff_factor: float = 1.5,
    jitter: float = 0.5,
    error_patterns: Optional[list[str]] = None,
) -> Callable:
    """Retry decorator that absorbs Dataverse metadata propagation delays.

    Args:
        max_retries: Maximum number of attempts.
        initial_delay: Initial delay in seconds.
        backoff_factor: Multiplier applied to the delay after each retry.
        jitter: Random jitter in seconds to avoid synchronized retries.
        error_patterns: Substrings that mark an error as retryable
            (defaults to DEFAULT_RETRY_PATTERNS).

    Returns:
        The decorated function.
    """
    if error_patterns is None:
        error_patterns = DEFAULT_RETRY_PATTERNS

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = initial_delay
            last_error: Optional[Exception] = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    should_retry = any(pattern in error_msg for pattern in error_patterns)

                    if should_retry and attempt < max_retries - 1:
                        actual_delay = delay + random.uniform(0, jitter)
                        logger.warning(
                            f"[Retry] {func.__name__} failed (attempt {attempt + 1}/{max_retries}): "
                            f"{e}. Retrying in {actual_delay:.1f}s..."
                        )
                        time.sleep(actual_delay)
                        delay *= backoff_factor
                        continue

                    if not should_retry:
                        logger.debug(f"[Retry] {func.__name__} failed with non-retryable error: {e}")
                    else:
                        logger.error(
                            f"[Retry] {func.__name__} failed after {max_retries} attempts: {e}"
                        )
                    raise

            if last_error:
                raise last_error
            raise RuntimeError("retry loop exited without a result")  # pragma: no cover

        return wrapper

    return decorator


def retry_on_404(max_retries: int = 5, initial_delay: float = 2.0) -> Callable:
    """Simplified retry decorator for 404 / not-found errors only."""
    return retry_on_metadata_error(
        max_retries=max_retries,
        initial_delay=initial_delay,
        error_patterns=["not found", "cannot be found", "404"],
    )


def wait_for(
    check_fn: Callable[..., Any],
    *args: Any,
    timeout: float = 30.0,
    check_interval: float = 2.0,
    description: str = "resource",
) -> Any:
    """Poll ``check_fn`` until it succeeds or ``timeout`` elapses.

    Args:
        check_fn: Function that returns metadata or raises while not ready.
        *args: Positional args forwarded to ``check_fn``.
        timeout: Total seconds to wait.
        check_interval: Seconds between attempts.
        description: Human-readable label for log messages.

    Returns:
        Whatever ``check_fn`` returns once it succeeds.

    Raises:
        MetadataPropagationError: If the resource is still unavailable after timeout.
    """
    start = time.time()
    last_error: Optional[Exception] = None
    while time.time() - start < timeout:
        try:
            result = check_fn(*args)
            logger.info(f"[Wait] {description} is now available")
            return result
        except Exception as e:  # noqa: BLE001 - intentional broad poll
            last_error = e
            logger.debug(f"[Wait] {description} not ready: {e}. Retrying...")
            time.sleep(check_interval)
    raise MetadataPropagationError(
        f"{description} not available after {timeout}s. Last error: {last_error}"
    )
