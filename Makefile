.PHONY: all up setup-db dev-api dev-airflow clean help

PYTHON := python3.11

up:
	docker compose up -d

dev: dev-api dev-airflow
	@echo ""
	@echo "=== ✓ Setup Complete ==="

dev-api:
	@echo "=== Setting API Development ==="
	@bash -c ' \
		source ~/.nvm/nvm.sh && \
		cd api && \
		nvm install && \
		nvm use && \
		if ! command -v pnpm >/dev/null 2>&1; then \
			echo "Installing pnpm..."; \
			npm install -g pnpm; \
		fi && \
		pnpm install'
	@echo "✓ API setup complete!"

dev-airflow:
	@echo "=== Setting up Airflow Environment ==="
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo "Error: $(PYTHON) not found"; exit 1; }
	cd airflow && \
		$(PYTHON) -m venv .venv && \
		.venv/bin/pip install --upgrade pip && \
		.venv/bin/pip install -r requirements.txt
	@echo "✓ Complete! Activate with: source airflow/.venv/bin/activate"

clean:
	@echo "=== Cleaning Docker Environment ==="
	docker compose down --volumes --remove-orphans --rmi all

rebuild-api-image:
	@echo "=== Rebuild API image ==="
	docker compose build --no-cache api
	docker compose up -d --no-deps --force-recreate api

rebuild-airflow-image:
	@echo "=== Rebuild shared Airflow image ==="
	docker compose build --no-cache airflow-init
	docker compose up -d --no-deps --force-recreate airflow-init airflow-webserver airflow-scheduler

help:
	@echo "Available targets:"
	@echo "  make up                    - Start services with Docker Compose"
	@echo "  make dev                   - Setup all development environments"
	@echo "  make dev-api               - Setup API development environment"
	@echo "  make dev-airflow           - Setup Airflow development environment"
	@echo "  make rebuild-api-image     - Rebuilds Docker image used by API"
	@echo "  make rebuild-airflow-image - Rebuilds Docker image used by AirFlow"
	@echo "  make clean                 - Stop and clean Docker resources"