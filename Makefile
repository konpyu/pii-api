.PHONY: format lint test type-check all

format:
	black .
	isort .

lint:
	flake8 .

type-check:
	mypy src/pii_masking tests --explicit-package-bases

test:
	pytest

all: format lint type-check test