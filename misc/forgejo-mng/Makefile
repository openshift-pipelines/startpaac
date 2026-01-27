.PHONY: help format lint check test clean

check: format lint

help:
	@echo "Available targets:"
	@echo "  format  - Format code with ruff"
	@echo "  lint    - Run ruff linter"
	@echo "  check   - Run format and lint checks"
	@echo "  test    - Test script execution"
	@echo "  clean   - Remove temporary files"

format:
	uv tool run ruff format main.py
	uv tool run ruff check --select I --fix main.py

lint:
	uv tool run ruff check main.py


test:
	./main.py --help

clean:
	rm -rf __pycache__ .ruff_cache
