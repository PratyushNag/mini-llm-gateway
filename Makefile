PYTHON ?= python

up:
	docker compose up --build

install:
	$(PYTHON) -m pip install -e .[dev]

seed-demo:
	$(PYTHON) -m scripts.seed_demo

demo-all:
	$(PYTHON) -m scripts.demo_walkthrough

test:
	$(PYTHON) -m pytest
