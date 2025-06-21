.PHONY: format lint test type-check all

format:
	black .
	isort .

lint:
	flake8 .

type-check:
	mypy src tests

test:
	pytest

all: format lint type-check test