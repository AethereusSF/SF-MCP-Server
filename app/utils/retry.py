"""Retry decorator with exponential backoff for resilient API calls

Created by Sameer
"""
import time
import logging
from functools import wraps
from typing import Callable, Type, Tuple, Optional

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Decorator that retries a function with exponential backoff.

    Added by Sameer

    Args:
        max_attempts: Maximum number of retry attempts
        backoff: Backoff multiplier (wait time = backoff ^ attempt)
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Optional callback function called on each retry

    Example:
        @retry(max_attempts=3, backoff=2.0, exceptions=(requests.RequestException,))
        def make_api_call():
            return requests.get("https://api.example.com")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    wait_time = backoff ** attempt
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    time.sleep(wait_time)

            return None  # Should never reach here
        return wrapper
    return decorator


def async_retry(
    max_attempts: int = 3,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Async version of retry decorator.

    Added by Sameer

    Example:
        @async_retry(max_attempts=3, backoff=2.0)
        async def make_async_api_call():
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.example.com") as resp:
                    return await resp.json()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import asyncio

            attempt = 0
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(
                            f"Async function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    wait_time = backoff ** attempt
                    logger.warning(
                        f"Async function {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )

                    await asyncio.sleep(wait_time)

            return None
        return wrapper
    return decorator
