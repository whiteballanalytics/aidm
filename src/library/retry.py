"""Retry logic for transient LLM failures with exponential backoff."""

import asyncio
import logging
from functools import wraps
from typing import TypeVar, Callable, Any, Awaitable

import openai

logger = logging.getLogger(__name__)

T = TypeVar('T')

TRANSIENT_EXCEPTIONS = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.InternalServerError,
)

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 8.0


def is_transient_error(exc: Exception) -> bool:
    """Check if an exception is transient and worth retrying."""
    if isinstance(exc, TRANSIENT_EXCEPTIONS):
        return True
    if isinstance(exc, openai.APIStatusError) and exc.status_code in (502, 503, 504):
        return True
    return False


def retry_on_transient(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for retrying async functions on transient LLM errors.
    
    Uses exponential backoff: delay doubles each attempt up to max_delay.
    Only retries on transient errors (rate limits, timeouts, server errors).
    Non-transient errors (auth, invalid request) fail immediately.
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exception = exc
                    
                    if not is_transient_error(exc):
                        logger.error(
                            "Non-transient error in %s: %s",
                            func.__name__, exc
                        )
                        raise
                    
                    if attempt == max_attempts:
                        logger.error(
                            "Max retries (%d) exceeded for %s: %s",
                            max_attempts, func.__name__, exc
                        )
                        raise
                    
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning(
                        "Retry %d/%d for %s after %s, waiting %.1fs...",
                        attempt, max_attempts, func.__name__,
                        type(exc).__name__, delay
                    )
                    await asyncio.sleep(delay)
            
            assert last_exception is not None
            raise last_exception
        
        return wrapper
    return decorator


async def run_with_retry(
    coro_func: Callable[..., Awaitable[T]],
    *args: Any,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    **kwargs: Any,
) -> T:
    """Run an async function with retry logic.
    
    Alternative to decorator when you need per-call configuration.
    
    Usage:
        result = await run_with_retry(Runner.run, agent, messages)
    """
    last_exception: Exception | None = None
    func_name = getattr(coro_func, '__name__', str(coro_func))
    
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_func(*args, **kwargs)
        except Exception as exc:
            last_exception = exc
            
            if not is_transient_error(exc):
                logger.error("Non-transient error in %s: %s", func_name, exc)
                raise
            
            if attempt == max_attempts:
                logger.error(
                    "Max retries (%d) exceeded for %s: %s",
                    max_attempts, func_name, exc
                )
                raise
            
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning(
                "Retry %d/%d for %s after %s, waiting %.1fs...",
                attempt, max_attempts, func_name,
                type(exc).__name__, delay
            )
            await asyncio.sleep(delay)
    
    assert last_exception is not None
    raise last_exception
