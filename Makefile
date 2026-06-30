.PHONY: install dev test lint typecheck format clean

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	python -m pytest tests/ -v

lint:
	ruff check behave_modern_json_report/ tests/
	ruff format --check behave_modern_json_report/ tests/

typecheck:
	mypy behave_modern_json_report/

format:
	ruff check --fix behave_modern_json_report/ tests/
	ruff format behave_modern_json_report/ tests/

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
