.PHONY: install test lint typecheck format ci sandbox-build clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install project with dev dependencies
	pip install -e ".[dev]" --break-system-packages

test: ## Run test suite
	pytest tests/ -v --cov=letsbuild --cov-report=term-missing

test-fast: ## Run tests excluding slow/integration
	pytest tests/ -v -m "not slow and not integration"

test-single: ## Run a single test file (usage: make test-single FILE=tests/intake/test_engine.py)
	pytest $(FILE) -v

lint: ## Run linter
	ruff check . --fix

typecheck: ## Run type checker
	mypy --strict letsbuild/

format: ## Format code
	ruff format .

ci: lint typecheck test ## Run full CI pipeline locally

sandbox-build: ## Build Docker sandbox image
	docker build -t letsbuild/sandbox:latest -f sandbox/Dockerfile .

benchmark: ## Run benchmark suite
	python -m letsbuild.benchmark run

audit: ## Security audit
	pip-audit
	ruff check . --select S
	@echo "Checking for hardcoded secrets..."
	@grep -rn "sk-ant-\|ghp_\|Bearer " letsbuild/ && echo "WARNING: Possible secrets found!" || echo "No secrets found."

docs: ## Build documentation site
	mkdocs build

docs-serve: ## Serve docs locally
	mkdocs serve

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info .mypy_cache .ruff_cache .pytest_cache htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
