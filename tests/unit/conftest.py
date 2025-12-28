# tests/unit/conftest.py
"""Shared pytest fixtures for unit tests."""

import os
import pytest


@pytest.fixture(autouse=True)
def set_test_api_key(monkeypatch):
    """Ensure OPENAI_API_KEY is set for tests that may instantiate OpenAI clients."""
    if not os.environ.get("OPENAI_API_KEY"):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-for-unit-tests")
