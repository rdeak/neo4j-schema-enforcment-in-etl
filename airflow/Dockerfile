FROM apache/airflow:2.7.3

USER root

RUN install -d -o 50000 -g 0 -m 775 \
      /opt/venvs \
      /opt/python \
      /opt/airflow/dags \
      /opt/airflow/plugins \
      /opt/tasks

USER airflow

ENV ETL_PYTHON=/opt/venvs/etl/bin/python

RUN --mount=from=ghcr.io/astral-sh/uv:0.12.7,source=/uv,target=/usr/local/bin/uv \
    --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    --mount=type=cache,target=/tmp/uv-cache,uid=50000,gid=0 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PYTHON_PREFERENCE=only-managed \
    uv venv --python 3.11 --seed /opt/venvs/etl \
 && uv pip install --python /opt/venvs/etl/bin/python -r /tmp/requirements.txt

WORKDIR /opt/airflow

COPY dags ./dags
COPY plugins ./plugins
COPY tasks /opt/tasks/tasks

RUN set -eu; \
    ETL_SP=$("$ETL_PYTHON" -Bc 'import sysconfig; print(sysconfig.get_paths()["purelib"])'); \
    echo /opt/tasks > "$ETL_SP/etl-runtime.pth"; \
    python -IBc "\
import sys, importlib.util as u; \
sys.path.insert(0, '/opt/airflow/dags'); \
assert u.find_spec('operators') is not None, 'operators must be importable from the DAGs folder'; \
assert u.find_spec('tasks') is None, 'tasks must NOT be importable from the Airflow runtime'; \
print('airflow runtime OK:', sys.version.split()[0], sys.prefix)"; \
    "$ETL_PYTHON" -IBc "\
import sys, importlib.util as u; \
assert '/opt/tasks' in sys.path, sys.path; \
assert u.find_spec('tasks') is not None, 'tasks must be importable from the ETL runtime'; \
assert u.find_spec('airflow') is None, 'airflow must NOT be installed in the ETL runtime'; \
assert u.find_spec('operators') is None, 'operators must NOT be importable from the ETL runtime'; \
print('ETL runtime OK:', sys.version.split()[0], sys.prefix)"
