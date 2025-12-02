# Testing Standards

This document outlines the standards and best practices for testing in this repository.

## Test Structure

```
tests/
├── TESTING.md          # This file
├── unit/               # Deterministic unit tests (isolated, mocked)
├── integration/        # (Future) Multi-function tests spanning components
└── evals/              # (Future) Non-deterministic evaluations for LLM routines
```

- **Unit tests** (`tests/unit/`) - Fast, deterministic tests for individual functions. All external dependencies are mocked.
- **Integration tests** (`tests/integration/`) - (Planned) Tests that exercise multiple functions working together, still with mocked LLM calls.
- **Evals** (`tests/evals/`) - (Planned) Non-deterministic evaluations that make real LLM calls to assess quality of AI responses, routing accuracy, etc.

## Core Principles

1. **Document actual behavior, not theoretical specs** - Tests should verify how the code actually works, not how we think it should work. If a test fails, either the code has regressed or the test was documenting incorrect behavior.

2. **Unit tests must be deterministic** - Never include LLM API calls or other non-deterministic operations in unit tests. Use mocks to provide predictable responses.

3. **Isolate from external dependencies** - Use `tmp_path` and `monkeypatch` fixtures to isolate file system operations. Use `unittest.mock` (AsyncMock, patch) to mock external services.

## Docstring Requirements

Every test function **must** have a one-sentence docstring that includes:
- The name of the function being tested
- A concise summary of what the test verifies

```python
def test_load_session_returns_none_for_missing(self, tmp_path, monkeypatch):
    """Tests load_session: returns None when session file does not exist."""
```

## Test Organization

- Unit tests live under `tests/unit/` organized by functionality
- Use descriptive class names grouping related tests (e.g., `TestLoadSession`, `TestCloseSession`)
- One test file per logical domain (e.g., `test_sessions.py`, `test_campaigns.py`, `test_orchestration.py`)

## Async Tests

- Use `pytest-asyncio` with `asyncio_mode = "auto"` (configured in `pyproject.toml`)
- Async test functions are detected automatically; no decorator needed

## Mocking Guidelines

- Mock at the boundary (e.g., `Runner.run` for LLM calls)
- Use `SimpleNamespace` for creating mock response objects
- Use `side_effect` for sequential mock returns

```python
with patch("orchestration.turn_router.Runner.run", new_callable=AsyncMock) as mock_run:
    mock_run.side_effect = [router_response, specialist_response]
```

## Running Tests

```bash
# Run all unit tests
python3.11 -m pytest tests/unit/ -v

# Run a specific test file
python3.11 -m pytest tests/unit/test_orchestration.py -v

# Run tests matching a pattern
python3.11 -m pytest tests/unit/ -k "orchestrate" -v
```
