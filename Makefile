.PHONY: test backend fixture

test:
	uv run pytest

backend:
	uv run coach-backend

fixture:
	uv run python scripts/replay_fixture.py
