.PHONY: all up dev dev-api dev-airflow test test-runtimes \
        rebuild-api-image rebuild-airflow-image clean help

AIRFLOW_DIR := airflow
PY_ETL      := 3.11

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
	@echo "=== Setting up the ETL runtime (Python $(PY_ETL), no Airflow) ==="
	@command -v uv >/dev/null 2>&1 || { echo "Error: uv not found - https://docs.astral.sh/uv/"; exit 1; }
	uv venv --clear --python $(PY_ETL) $(AIRFLOW_DIR)/.venv
	uv pip install --python $(AIRFLOW_DIR)/.venv/bin/python \
		-r $(AIRFLOW_DIR)/pyproject.toml \
		--group $(AIRFLOW_DIR)/pyproject.toml:dev
	@echo "✓ ETL runtime ready: $(AIRFLOW_DIR)/.venv"

test:
	@echo "=== ETL task tests (Postgres and the API stubbed) ==="
	cd $(AIRFLOW_DIR) && { .venv/bin/python -m pytest || [ $$? -eq 5 ]; }

test-runtimes:
	@echo "=== In-container source roots ==="
	docker compose run --rm --no-deps --entrypoint python airflow-scheduler -IBc "import sys, importlib.util as u; sys.path.insert(0, '/opt/airflow/dags'); assert u.find_spec('operators') is not None, 'operators missing'; assert u.find_spec('tasks') is None, 'tasks leaked into the Airflow runtime'; print('airflow runtime OK:', sys.version.split()[0])"
	docker compose run --rm --no-deps --entrypoint /opt/venvs/etl/bin/python airflow-scheduler -IBc "import sys, importlib.util as u; assert u.find_spec('tasks') is not None, 'tasks missing'; assert u.find_spec('airflow') is None, 'airflow leaked into the ETL runtime'; assert u.find_spec('operators') is None, 'operators leaked into the ETL runtime'; print('ETL runtime OK:', sys.version.split()[0])"

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
	@echo "  make dev-airflow           - Setup airflow/.venv (Python $(PY_ETL), the ETL runtime)"
	@echo "  make test                  - Run the ETL task tests"
	@echo "  make test-runtimes         - Verify the source roots inside the running image"
	@echo "  make rebuild-api-image     - Rebuilds Docker image used by API"
	@echo "  make rebuild-airflow-image - Rebuilds Docker image used by AirFlow"
	@echo "  make clean                 - Stop and clean Docker resources"
