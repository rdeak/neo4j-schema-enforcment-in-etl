# Airflow

One directory, one manifest, two interpreters — and the second interpreter is
something the image builds, not something this repo mirrors on your machine.

|                   | `dags/`                                                        | `tasks/`                                            |
|-------------------|----------------------------------------------------------------|-----------------------------------------------------|
| Runs on           | Airflow's own Python **3.8** (`apache/airflow:2.7.3` ships it) | **`$ETL_PYTHON`** — Python 3.11 at `/opt/venvs/etl` |
| Airflow installed | yes, plus providers                                            | **no**                                              |
| Holds             | the DAG, plus `operators/` — the Airflow-side helpers          | the task bodies: the SQL, the mutation              |
| Manifest          | none — the base image is the manifest                          | `requirements.txt`, via `pyproject.toml`            |
| Path in the image | `/opt/airflow/dags`                                            | `/opt/tasks/tasks`                                  |
| Exercised by      | Airflow, in a container                                        | `make test`                                         |

## Why two interpreters

The Airflow image pins its own interpreter and a large, tightly constrained
dependency tree. Pipeline code wants a different one — a current pandas, a
current `gql` — and upgrading either half in place means fighting the other. So
the pipeline gets its own interpreter, built by `uv` in `Dockerfile`, and task
dependencies move independently of the scheduler's. Nothing about the ETL code
needs Airflow; the split makes that literal rather than aspirational.

## Why only one manifest

`requirements.txt` describes `$ETL_PYTHON` and nothing else; `pyproject.toml`
references it (`dynamic = ["dependencies"]` +
`[tool.setuptools.dynamic]`) and adds the `dev` group and the pytest settings.
There is no second manifest for the Airflow side, and no host venv that pretends
to be one.

Airflow's half is not reproducible off the scheduler anyway: `ExternalPythonOperator`
extracts a decorated function's source, ships it to another interpreter and runs
it there, and the surrounding machinery — DAG parsing, XCom, the connection
lookups — is Airflow executing in its own container. A local Airflow venv can
make the imports resolve in an editor, but it can't run any of that without a
pile of scaffolding that then has to be kept true. So `dags/` is exercised where
it actually runs, and the one venv here is the ETL one.

## Layout

```
airflow/
├── Dockerfile                       builds BOTH interpreters into one image
├── README.md                        this file
├── requirements.txt                 the one manifest: $ETL_PYTHON's dependencies
├── pyproject.toml                   references it; holds the dev group and pytest config
├── plugins/                         Airflow's plugins folder - mounted, not a source root
├── scripts/init-airflow.sh          bash; seeds the Airflow connections
│
├── dags/                            ▸ Airflow's runtime · Python 3.8
│   ├── process_invoices.py          wiring, plus two-line shims across the boundary
│   └── operators/isolated_task.py   the decorator that crosses the boundary
│
├── tasks/                           ▸ $ETL_PYTHON · Python 3.11 · no Airflow
│   ├── extract.py                   the SQL, and the read into records
│   └── load.py                      the createInvoices mutation
│
└── tests/                           tests for tasks/ (none checked in yet)
```

`operators/` sits *inside* `dags/` because Airflow appends its DAGs folder to
`sys.path` (`settings.prepare_syspath`). That is the whole reason
`from operators.isolated_task import isolated_task` resolves — no `.pth`, no
`PYTHONPATH`, nothing to configure.

## How a task crosses the boundary

`@isolated_task` (`dags/operators/isolated_task.py`) is a thin wrapper over
Airflow's `ExternalPythonOperator`, pinned to `python=$ETL_PYTHON` and
`expect_airflow=False`. Airflow **extracts the decorated function's source** and
re-executes it under the other interpreter — the body is not a closure over this
module.

```
   Airflow runtime (3.8)                    $ETL_PYTHON (3.11)
   ─────────────────────                    ──────────────────
   resolve_connections   ──XCom (plain dict)──▶
        hooks, providers                        extract_invoices  ─▶ tasks.extract
                                                load_to_neo4j     ─▶ tasks.load
```

That gives the pipeline three rules, all load-bearing:

- **Airflow is unavailable inside an isolated task.** Hence `resolve_connections`:
  hooks run in Airflow's own runtime and hand plain connection details down through
  XCom. (This puts the Postgres password in XCom — fine for a local demo with
  hardcoded `airflow`/`airflow`, not a pattern to copy.)
- **Every import in a task body must be local.** Module-level imports in the DAG
  file are not visible to the extracted source. Keeping the bodies to two lines —
  import from `tasks`, call it — means there is almost nothing there to get wrong,
  and the real logic stays plain, importable, testable Python.
- **`custom_operator_name = "@isolated_task"`** is what lets Airflow strip the
  decorator line from the extracted source. Rename the decorator without updating
  it and the task breaks at run time, not at parse time.

The DAG module also carries `from __future__ import annotations`, because it is
parsed by Python 3.8 where `list[dict]` is not a valid runtime annotation.

## What enforces the separation

Each interpreter gets one source root, and only one of them needs help:

| Interpreter        | Source root         | Put there by      | Can import             | Cannot import          |
|--------------------|---------------------|-------------------|------------------------|------------------------|
| Airflow 3.8        | `/opt/airflow/dags` | Airflow itself    | `operators`, `airflow` | `tasks`                |
| `$ETL_PYTHON` 3.11 | `/opt/tasks`        | `etl-runtime.pth` | `tasks`                | `operators`, `airflow` |

The image build asserts all of those, positively and negatively, so a broken
mount or a missing directory fails `docker compose build` instead of surfacing as
a `ModuleNotFoundError` halfway through a DAG run. `site.addpackage()` silently
drops path entries pointing at directories that do not exist, which is why the
`install -d` in the `Dockerfile` has to stay ahead of the `.pth` write.

`docker-compose.yml` bind-mounts the host directories onto those same container
paths, so the container contract (`/opt/airflow/dags`, `/opt/tasks/tasks`) is
stable no matter how this directory is arranged.

## Local development

Prerequisite: [`uv`](https://docs.astral.sh/uv/). It fetches the 3.11
interpreter, so you do not need one installed yourself.

```bash
make dev-airflow    # airflow/.venv — Python 3.11, the dependencies in requirements.txt + pytest
```

That venv is `$ETL_PYTHON`'s counterpart on your machine: the same
`requirements.txt` the `Dockerfile` installs into `/opt/venvs/etl`, plus the
`dev` group from `pyproject.toml`. It is what runs `make test` and what your editor should resolve
`tasks/` against.

It is **not** an Airflow environment. `from airflow.decorators import dag` will
show up unresolved in `dags/process_invoices.py`, and that is the accurate
picture — see *Why only one manifest*.

## Tests

```bash
make test           # tasks/, with Postgres and the API stubbed
make test-runtimes  # asks each in-container interpreter what it can import
```

`tests/` is empty right now, so `make test` collects nothing — the target
tolerates pytest's exit code 5 for exactly that reason, and the tolerance can go
once something lands there. Host tests cannot see the image's `.pth` file or the compose mounts,
which is what `make test-runtimes` covers — it runs both in-container interpreters
and checks what each one can and cannot import.

Nothing here touches Postgres, Neo4j, or the API; `make test` runs with nothing
started.

## IDE setup

One SDK — `airflow/.venv` (3.11) — and two source roots inside `airflow/`:

| Directory       | Mark as           | So that                                                     |
|-----------------|-------------------|-------------------------------------------------------------|
| `airflow/`      | sources root      | `tasks.extract` and `tasks.load` resolve                    |
| `airflow/dags`  | sources root      | `operators.isolated_task` resolves, the way Airflow does it |
| `airflow/tests` | test sources root | pytest and the editor agree                                 |

`[tool.pytest.ini_options].pythonpath` in `pyproject.toml` gives pytest the first
of those without anything being pip-installed.

Two things the editor will get wrong, and both are expected:

- **`from airflow.decorators import dag` is unresolved.** Airflow is not in this
  venv on purpose.
- **`from tasks.extract import ...` inside a task body resolves.** With one module
  the editor can no longer model the boundary — that line is source text destined
  for the other interpreter, not an import this file makes. The boundary is
  enforced in the image (see *What enforces the separation*), not in your editor.

## Changing dependencies

`requirements.txt` is the only manifest, and it feeds both the image and your
venv:

```bash
make rebuild-airflow-image   # rebuilds /opt/venvs/etl from requirements.txt
make dev-airflow             # rebuilds airflow/.venv from the same file, reached through
                             # pyproject.toml's reference, + the dev group
```

Three of the pins are not ETL dependencies and should stay:
`pendulum`, `lazy-object-proxy` and `dill` are held at the versions
`apache/airflow:2.7.3` ships so that arguments and return values pickled by
Airflow round-trip through the venv unchanged. Bumping the Airflow version means
revisiting them alongside the `FROM` line in `Dockerfile` — which, since there is
no second manifest, is now the only place the Airflow version is written.
