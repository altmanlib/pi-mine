.PHONY: sync fmt lint typecheck test check

sync:
	uv sync

fmt:
	uv run ruff format app tests
	uv run ruff check --fix app tests

lint:
	uv run ruff check app tests

typecheck:
	uv run pyright

test:
	uv run pytest -v

check: lint typecheck test
