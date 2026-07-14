.PHONY: install run-api run-bot run-cleanup test docker-up lint clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -e ".[dev]"

run-api: ## Start the FastAPI server
	python -m ytdl_platform.main api

run-bot: ## Start the Telegram bot
	python -m ytdl_platform.main bot

run-cleanup: ## Start the cleanup worker
	python -m ytdl_platform.main cleanup

test: ## Run tests
	pytest -v

lint: ## Run linter
	ruff check src/ tests/

docker-up: ## Build and start Docker Compose
	docker compose up --build -d

docker-down: ## Stop Docker Compose
	docker compose down

clean: ## Remove generated files
	rm -rf data/ __pycache__/ .pytest_cache/ *.egg-info dist build

.DEFAULT_GOAL := help
