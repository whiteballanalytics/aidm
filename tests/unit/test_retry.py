"""Unit tests for src/library/retry.py - retry logic for transient LLM failures."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import openai

from src.library.retry import (
    is_transient_error,
    retry_on_transient,
    run_with_retry,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_BASE_DELAY,
)


class TestIsTransientError:
    """Tests for is_transient_error() function."""

    def test_rate_limit_error_is_transient(self):
        """is_transient_error returns True for RateLimitError."""
        exc = openai.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body=None
        )
        assert is_transient_error(exc) is True

    def test_api_timeout_error_is_transient(self):
        """is_transient_error returns True for APITimeoutError."""
        exc = openai.APITimeoutError(request=MagicMock())
        assert is_transient_error(exc) is True

    def test_api_connection_error_is_transient(self):
        """is_transient_error returns True for APIConnectionError."""
        exc = openai.APIConnectionError(request=MagicMock())
        assert is_transient_error(exc) is True

    def test_internal_server_error_is_transient(self):
        """is_transient_error returns True for InternalServerError."""
        exc = openai.InternalServerError(
            message="Internal server error",
            response=MagicMock(status_code=500),
            body=None
        )
        assert is_transient_error(exc) is True

    def test_bad_gateway_502_is_transient(self):
        """is_transient_error returns True for 502 Bad Gateway."""
        exc = openai.APIStatusError(
            message="Bad Gateway",
            response=MagicMock(status_code=502),
            body=None
        )
        assert is_transient_error(exc) is True

    def test_service_unavailable_503_is_transient(self):
        """is_transient_error returns True for 503 Service Unavailable."""
        exc = openai.APIStatusError(
            message="Service Unavailable",
            response=MagicMock(status_code=503),
            body=None
        )
        assert is_transient_error(exc) is True

    def test_gateway_timeout_504_is_transient(self):
        """is_transient_error returns True for 504 Gateway Timeout."""
        exc = openai.APIStatusError(
            message="Gateway Timeout",
            response=MagicMock(status_code=504),
            body=None
        )
        assert is_transient_error(exc) is True

    def test_auth_error_is_not_transient(self):
        """is_transient_error returns False for AuthenticationError."""
        exc = openai.AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body=None
        )
        assert is_transient_error(exc) is False

    def test_bad_request_400_is_not_transient(self):
        """is_transient_error returns False for 400 Bad Request."""
        exc = openai.APIStatusError(
            message="Bad Request",
            response=MagicMock(status_code=400),
            body=None
        )
        assert is_transient_error(exc) is False

    def test_not_found_404_is_not_transient(self):
        """is_transient_error returns False for 404 Not Found."""
        exc = openai.APIStatusError(
            message="Not Found",
            response=MagicMock(status_code=404),
            body=None
        )
        assert is_transient_error(exc) is False

    def test_generic_exception_is_not_transient(self):
        """is_transient_error returns False for generic Exception."""
        exc = Exception("Something went wrong")
        assert is_transient_error(exc) is False

    def test_value_error_is_not_transient(self):
        """is_transient_error returns False for ValueError."""
        exc = ValueError("Invalid value")
        assert is_transient_error(exc) is False


class TestRetryOnTransientDecorator:
    """Tests for retry_on_transient decorator."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """retry_on_transient returns result immediately on first success."""
        @retry_on_transient()
        async def successful_func():
            return "success"

        result = await successful_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        """retry_on_transient retries on transient error then returns on success."""
        call_count = 0

        @retry_on_transient(base_delay=0.01)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise openai.RateLimitError(
                    message="Rate limit",
                    response=MagicMock(status_code=429),
                    body=None
                )
            return "success"

        result = await flaky_func()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """retry_on_transient raises after max attempts exceeded."""
        call_count = 0

        @retry_on_transient(max_attempts=3, base_delay=0.01)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise openai.RateLimitError(
                message="Rate limit",
                response=MagicMock(status_code=429),
                body=None
            )

        with pytest.raises(openai.RateLimitError):
            await always_fails()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_transient_error_raises_immediately(self):
        """retry_on_transient raises immediately for non-transient errors."""
        call_count = 0

        @retry_on_transient(base_delay=0.01)
        async def auth_error_func():
            nonlocal call_count
            call_count += 1
            raise openai.AuthenticationError(
                message="Invalid API key",
                response=MagicMock(status_code=401),
                body=None
            )

        with pytest.raises(openai.AuthenticationError):
            await auth_error_func()

        assert call_count == 1


class TestRunWithRetry:
    """Tests for run_with_retry function."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """run_with_retry returns result immediately on first success."""
        async def successful_func(arg1, arg2):
            return f"{arg1}-{arg2}"

        result = await run_with_retry(successful_func, "hello", "world")
        assert result == "hello-world"

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        """run_with_retry retries on transient error then returns on success."""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise openai.APITimeoutError(request=MagicMock())
            return "success"

        result = await run_with_retry(flaky_func, base_delay=0.01)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """run_with_retry raises after max attempts exceeded."""
        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise openai.APIConnectionError(request=MagicMock())

        with pytest.raises(openai.APIConnectionError):
            await run_with_retry(always_fails, max_attempts=2, base_delay=0.01)

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_non_transient_error_raises_immediately(self):
        """run_with_retry raises immediately for non-transient errors."""
        call_count = 0

        async def bad_request_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Bad input")

        with pytest.raises(ValueError):
            await run_with_retry(bad_request_func, base_delay=0.01)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_passes_kwargs(self):
        """run_with_retry correctly passes keyword arguments."""
        async def func_with_kwargs(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = await run_with_retry(func_with_kwargs, "x", "y", c="z")
        assert result == "x-y-z"


class TestExponentialBackoff:
    """Tests for exponential backoff timing."""

    @pytest.mark.asyncio
    async def test_backoff_delays_increase(self):
        """retry_on_transient uses exponential backoff delays."""
        delays = []

        async def mock_sleep(delay):
            delays.append(delay)

        call_count = 0

        @retry_on_transient(max_attempts=4, base_delay=1.0, max_delay=8.0)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise openai.RateLimitError(
                message="Rate limit",
                response=MagicMock(status_code=429),
                body=None
            )

        with patch('asyncio.sleep', mock_sleep):
            with pytest.raises(openai.RateLimitError):
                await always_fails()

        assert delays == [1.0, 2.0, 4.0]

    @pytest.mark.asyncio
    async def test_backoff_respects_max_delay(self):
        """retry_on_transient caps delay at max_delay."""
        delays = []

        async def mock_sleep(delay):
            delays.append(delay)

        call_count = 0

        @retry_on_transient(max_attempts=5, base_delay=1.0, max_delay=3.0)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise openai.RateLimitError(
                message="Rate limit",
                response=MagicMock(status_code=429),
                body=None
            )

        with patch('asyncio.sleep', mock_sleep):
            with pytest.raises(openai.RateLimitError):
                await always_fails()

        assert delays == [1.0, 2.0, 3.0, 3.0]
