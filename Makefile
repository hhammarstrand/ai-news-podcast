.PHONY: help setup dev test lint run

help:
	@echo "Available targets:"
	@echo "  setup   - Install Python deps and start local services"
	@echo "  dev     - Start local PostgreSQL"
	@echo "  test    - Run tests with coverage"
	@echo "  lint    - Run ruff linter + mypy"
	@echo "  run     - Run the pipeline once (generates one episode)"

setup:
	cd pipeline && python -m venv .venv && .venv/bin/pip install -r requirements.txt
	cp -n pipeline/.env.example pipeline/.env || true
	docker-compose up -d postgres
	@echo "\nSetup complete! Edit pipeline/.env with your API keys, then run: make run"

dev:
	docker-compose up -d postgres

test:
	cd pipeline && .venv/bin/pytest --cov=src --cov-report=term-missing -v

lint:
	cd pipeline && .venv/bin/ruff check src tests && .venv/bin/mypy src

run:
	cd pipeline && .venv/bin/python -m src.main
