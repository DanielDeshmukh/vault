.PHONY: help install lint format typecheck test test-unit test-integration test-security test-all coverage clean docker-up docker-down

# Default target
help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================
# Setup
# ============================================

install: ## Install all dependencies
	cd backend && poetry install
	cd frontend && npm install
	pre-commit install

# ============================================
# Linting & Formatting
# ============================================

lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Run Python linters (ruff)
	cd backend && ruff check . --fix
	cd backend && ruff format .

lint-frontend: ## Run JavaScript/TypeScript linters (eslint)
	cd frontend && npm run lint -- --fix

format: format-backend ## Format all code

format-backend: ## Format Python code (ruff)
	cd backend && ruff format .

# ============================================
# Type Checking
# ============================================

typecheck: typecheck-backend typecheck-frontend ## Run all type checkers

typecheck-backend: ## Run Python type checker (mypy)
	cd backend && mypy app/

typecheck-frontend: ## Run TypeScript type checker
	cd frontend && npx tsc --noEmit

# ============================================
# Testing
# ============================================

test: test-all ## Run all tests

test-unit: ## Run unit tests
	cd backend && pytest tests/unit/ -v --tb=short

test-integration: ## Run integration tests
	cd backend && pytest tests/integration/ -v --tb=short

test-security: ## Run security tests
	cd backend && pytest tests/security/ -v --tb=short

test-eval: ## Run evaluation suite
	cd backend && python -m eval.run

test-all: ## Run all tests with coverage
	cd backend && pytest tests/ -v --tb=short --cov=app --cov-report=html --cov-report=xml

coverage: ## Generate and open coverage report
	cd backend && coverage html
	@echo "Open htmlcov/index.html in your browser"

# ============================================
# Docker
# ============================================

docker-up: ## Start Docker services
	docker-compose up -d

docker-down: ## Stop Docker services
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

# ============================================
# Development
# ============================================

dev-backend: ## Start backend development server
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start frontend development server
	cd frontend && npm run dev

dev: ## Start all development servers
	@echo "Starting backend and frontend..."
	@make dev-backend & make dev-frontend

# ============================================
# Database
# ============================================

db-migrate: ## Run database migrations
	cd backend && alembic upgrade head

db-revision: ## Create new migration
	cd backend && alembic revision --autogenerate -m "$(msg)"

db-seed: ## Seed default roles
	cd backend && python scripts/seed_roles.py

# ============================================
# Cleaning
# ============================================

clean: ## Clean generated files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name htmlcov -exec rm -rf {} +
	find . -type f -name "coverage.xml" -delete
	cd frontend && rm -rf .next out node_modules/.cache
