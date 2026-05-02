dev:
	pip install poetry
	poetry install --with dev

test:
	poetry run pytest tests/ -v

typecheck:
	poetry run mypy pyt/ --ignore-missing-imports

upload:
	poetry build
	twine upload dist/*

help:
	@echo "dev        - install all dependencies"
	@echo "test       - run the test suite"
	@echo "typecheck  - run mypy"
	@echo "upload     - build and publish to PyPI"
	@echo "clean      - remove build and cache artifacts"
	@echo "install    - install the package in editable mode"

clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +
	find . -name '*.DS_Store' -exec rm -f {} +

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

install: clean
	pip install -e .
