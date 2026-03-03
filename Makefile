UV ?= uv

up:
	docker compose up --build

install:
	$(UV) sync --extra dev

hooks:
	$(UV) run pre-commit install

seed-demo:
	$(UV) run python -m scripts.seed_demo

demo-all:
	$(UV) run python -m scripts.demo_walkthrough

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run mypy .
