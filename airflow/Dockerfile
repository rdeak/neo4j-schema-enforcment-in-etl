FROM apache/airflow:2.7.3

USER root

RUN install -d -o 50000 -g 0 -m 775 /opt/venvs /opt/python /opt/airflow/dags /opt/airflow/common

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

USER root

RUN set -eu; \
    for PY in python /opt/venvs/etl/bin/python; do \
      SP=$("$PY" -Bc 'import sysconfig; print(sysconfig.get_paths()["purelib"])'); \
      printf '%s\n%s\n' /opt/airflow/dags /opt/airflow/common > "$SP/airflow-shared.pth"; \
      echo "wrote $SP/airflow-shared.pth"; \
      "$PY" -Bc "\
import sys; \
assert '/opt/airflow/dags' in sys.path, sys.path; \
assert '/opt/airflow/common' in sys.path, sys.path; \
print('shared path OK:', sys.version.split()[0], sys.prefix)"; \
    done

USER airflow

WORKDIR /opt/airflow

COPY dags ./dags
COPY common ./common
