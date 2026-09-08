# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A demonstration that a Neo4j schema, expressed as GraphQL type definitions and enforced as database
constraints, is what stops an ETL pipeline from writing duplicates — not the pipeline itself. Postgres
holds the source invoices, Airflow extracts them, and the only write path into Neo4j is the GraphQL API.

## Commands

Everything runs through Docker Compose; `make help` lists the targets.

| Command                      | What it does                                                                                                                                     |
|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| `make up`                    | `docker compose up -d` — starts Neo4j, Postgres, the API, and Airflow                                                                            |
| `make clean`                 | Tears down containers, volumes, and images                                                                                                       |
| `make dev`                   | Host-side dev setup: pnpm install in `api/`, plus the one Airflow-side venv                                                                      |
| `make dev-airflow`           | `airflow/.venv` — uv builds Python 3.11 from `airflow/requirements.txt` (through the pyproject reference) plus its `dev` group, no Airflow in it |
| `make test`                  | pytest over `airflow/tests/`; `make test-runtimes` checks the in-image source roots                                                              |
| `make rebuild-api-image`     | Rebuild + recreate only the `api` service                                                                                                        |
| `make rebuild-airflow-image` | Rebuild the shared Airflow image, recreate init/webserver/scheduler                                                                              |

In `api/` (Node 24 via `.nvmrc`, pnpm 11 via corepack and `packageManager`):

- `pnpm dev` — runs `tsc --watch` and `node --watch dist/index.js` concurrently (this is also the
  container's `CMD`; the `api` service is a dev container, not a production build)
- `pnpm build` — `tsc` to `dist/`
- `pnpm rebuild-schema` — see "Two API entry points" below

In `api/` there are **no tests and no lint script**. Prettier is a devDependency with no npm script;
invoke it as `pnpm exec prettier`. Don't invent test commands there. `airflow/tests/` exists and
`make test` points pytest at it, but nothing is checked in yet, so it currently collects zero tests.

### Running the pipeline end to end

`AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION` is `true`, so after `make up` the `process_invoices` DAG
must be unpaused (or triggered manually) in the Airflow UI at http://localhost:8080 before anything
moves.

## Architecture

```
Postgres (db `app`)  --PostgresHook-->  Airflow DAG  --GraphQL mutation-->  Apollo/@neo4j/graphql  -->  Neo4j (db `data`)
```

**Postgres is the source of truth.** `docker-assets/postgres/init.sh` creates a second database `app`
alongside Airflow's own metadata db, and `init.sql` builds `invoices` / `invoice_items` there from the
CSVs in `docker-assets/postgres/csv/`. Note the `COPY` column lists are **positional** — `HEADER true`
skips the header line but does not match on names, so the CSV column order must line up with the column
list, not with the header text.

**The API (`api/src/index.ts`) is schema-first.** It loads `api/graphql/**/*.graphql` into
`Neo4jGraphQL`, which generates the full CRUD surface (`createInvoices`, `invoices`, etc.), then calls
`assertIndexesAndConstraints({ create: true })` at boot. That call is what turns the `@unique` directive
in the SDL into a real Neo4j constraint. Per-request `sessionConfig.database` pins queries to
`NEO4J_BASE`.

**The DAG (`airflow/dags/process_invoices.py`)** has three tasks and holds only the
wiring. `resolve_connections` is a plain `@task` that looks up `app_pg_conn` / `api_graphql_conn` and
returns them as a plain dict. `extract_invoices` and `load_to_neo4j` are two-line shims that import and
call the real implementations, which run on the other interpreter as `tasks.extract` and `tasks.load`
(`airflow/tasks/`).

`tasks/extract.py` runs one SQL query that pre-shapes each row into the exact nested `InvoiceCreateInput`
shape (the `json_build_object(...)` with a `create`/`node` structure is GraphQL input, not a Postgres
convention). `tasks/load.py` then loops the rows through the auto-generated `createInvoices` mutation over
HTTP.

### `airflow/` is two interpreters, and the directory names say which

`airflow/README.md` is the full account; the short version:

|                          | `airflow/dags/`                                       | `airflow/tasks/`                                                |
|--------------------------|-------------------------------------------------------|-----------------------------------------------------------------|
| Python                   | **3.8** (from `apache/airflow:2.7.3`)                 | **3.11** (uv-built `/opt/venvs/etl`, `$ETL_PYTHON`)             |
| Airflow                  | installed                                             | **not installed**                                               |
| Source root in the image | `/opt/airflow/dags` → `process_invoices`, `operators` | `/opt/tasks` → `tasks`                                          |
| Manifest                 | none — the base image is the manifest                 | `airflow/requirements.txt`, wrapped by `airflow/pyproject.toml` |
| Host venv                | none, deliberately                                    | `airflow/.venv` via `make dev-airflow`                          |

**There is exactly one `pyproject.toml` under `airflow/`, and it describes the 3.11 side.** Don't add a
second one for Airflow: the base image already ships that tree, and the part that matters — Airflow
extracting an `@isolated_task` body and re-running it under another interpreter — needs real Airflow in
a container, not a host venv. So `airflow/.venv` is the ETL interpreter's counterpart, `from airflow…`
is unresolved in the editor by design, and `dags/` is exercised by running the stack.

**The dependency list itself is `airflow/requirements.txt`.** The pyproject declares
`dynamic = ["dependencies"]` and points `[tool.setuptools.dynamic]` at that file, so the two never drift.
The Dockerfile installs `-r requirements.txt` directly; `make dev-airflow` installs `-r pyproject.toml` and
therefore resolves *through* the reference, which is what keeps it honest. That path needs a build backend
— hence the `[build-system]` block — and `packages = []`, without which setuptools' flat-layout discovery
trips over `dags/`, `tasks/` and `plugins/` sitting beside the manifest. It also leaves an ignored
`etl_tasks.egg-info/` behind.

`extract_invoices` and `load_to_neo4j` are decorated with `@isolated_task`
(`airflow/dags/operators/isolated_task.py`), a thin wrapper over `ExternalPythonOperator`
that pins `python=$ETL_PYTHON` and `expect_airflow=False`. So task dependencies, and the interpreter
itself, move independently of the scheduler's.

Each interpreter gets one source root. Airflow appends its own DAGs folder to `sys.path`
(`settings.prepare_syspath`), which is why `operators/` lives *inside* `dags/` and needs no help; the ETL
interpreter gets `/opt/tasks` from a single `.pth`. The Airflow interpreter cannot import `tasks`, and the
ETL interpreter cannot import `operators` or `airflow`. The image build asserts all of that in both
directions and fails if it stops being true.

Three consequences, all load-bearing:

- **Airflow imports are unavailable inside an isolated task.** That is why `resolve_connections`
  exists: hooks run in the Airflow environment and hand plain connection details down through XCom. (This does put the
  Postgres password in XCom — fine for a local demo with hardcoded
  `airflow` / `airflow`, not a pattern to copy to a real deployment.)
- **The task body is extracted as source and re-executed**, not closed over. Every import must live
  inside the function; module-level imports in the DAG file are not visible to it. That is why the
  bodies are two-line shims — one local import from `etl`, one call — and why the real logic lives in
  plain modules that can be imported and tested without Airflow. This is also why the DAG module
  carries `from __future__ import annotations`: `list[dict]` has to survive parsing on 3.8, and
  swapping in `typing.List` would `NameError` in the venv, where the future import and the module's
  imports are both absent.
- **`custom_operator_name = "@isolated_task"`** is what lets Airflow strip the decorator line from
  that extracted source. Renaming the decorator without updating it breaks the task at run time, not
  at parse time — nothing catches that pairing statically.

### The duplicate-data behaviour is the point

`Invoice.id` is declared `@unique(constraintName: "invoice_unique_idx")`, the constraint is created at
API boot, the DAG calls `createInvoices` (a plain create, not an upsert), and the DAG is `@daily` with
`retries: 2`. So the first run loads cleanly and every rerun fails on the constraint. This is intended
demonstration behaviour, not a bug to fix silently — if a task asks for idempotent loading, that is a
deliberate design change.

`upsertInvoices` in `invoice.graphql` is **dead and broken**: it `MERGE`s on `invoice.no`, but `Invoice`
has no `no` field, so `$input.no` is always null. Nothing calls it. Treat it as an abandoned attempt at
the fix above rather than a working upsert path.

## Details that bite

- **Neo4j database is `data`, not the default `neo4j`.** The one-shot `neo4j-init` compose service
  creates it; the API selects it via `NEO4J_BASE`. In Neo4j Browser (http://localhost:7474/browser/?db=data) you must
  switch databases or your Cypher hits an empty graph.
- **Compose gates the API on `neo4j-init`, not just on Neo4j being healthy.** Per-request
  `sessionConfig.database` pins queries to `data`, so `api` waits for the one-shot that creates that
  database (`service_completed_successfully`). All five long-running services carry healthchecks; the
  scheduler's depends on `AIRFLOW__SCHEDULER__ENABLE_HEALTH_CHECK`, which serves `/health` on 8974.
- **`airflow/.env` is an optional, uncommitted env file** (`required: false`, so its absence is fine).
  Compose gives `environment:` precedence over `env_file:`, so it can only *add* variables - it will
  not override the Fernet key or webserver secret set inline. On Linux, set `AIRFLOW_UID` to your own
  UID so files written into the mounted `dags/` are not root-owned; macOS can leave the 50000 default.
- **pnpm 10+ blocks dependency build scripts and treats an unapproved one as an install *failure*.**
  `api/pnpm-workspace.yaml` approves `esbuild` (needed by tsx, so by
  `pnpm rebuild-schema`) and `@apollo/protobufjs` via `allowBuilds`. Note that pnpm reads this from
  `pnpm-workspace.yaml`, not from a `pnpm` key in `package.json`.
- **`api/.dockerignore` is load-bearing.** Without it `COPY . .` drops the host's `node_modules` over
  the one installed in the image, and pnpm's pre-run dependency check then aborts with
  `ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY` in the TTY-less container.
- **The api image installs `--frozen-lockfile`**, so a `package.json` change that is not reflected in
  `api/pnpm-lock.yaml` fails the build instead of quietly resolving a different tree. Regenerate the
  lockfile with `pnpm install --lockfile-only` after editing dependencies.
- **`InvoiceItem` carries two labels**: `@node(labels: ["InvoiceItem", "PGInvoice"])`. Hand-written
  Cypher matching only `:InvoiceItem` still works, but the stored nodes have both.
- **Two API entry points.** `index.ts` serves the hand-written SDL on port 4000. `rebuild-schema.ts`
  (`pnpm rebuild-schema`) is a one-off that introspects the *live* graph with `@neo4j/introspector` in
  readonly mode and serves the result — despite the name it writes nothing to disk, so it is not a
  codegen step for `api/graphql/`.
- **Two Neo4j hosts.** `api/.env` points at `bolt://localhost:7687` for running the API on the host;
  compose overrides `NEO4J_HOST` to `bolt://neo4j:7687` inside the network.
- **The Airflow image builds a second interpreter.** `airflow/Dockerfile` uses uv to create
  `/opt/venvs/etl` from `airflow/requirements.txt` (bind-mounted for that one layer — neither it nor
  `pyproject.toml` is COPYed into the image) and exports `ETL_PYTHON` pointing at it. It then writes one `.pth` —
  `etl-runtime.pth` (`/opt/tasks`) into that venv's site-packages.
  The Airflow interpreter gets no `.pth`; it reaches `operators` through the DAGs folder Airflow puts
  on `sys.path` itself. `site.addpackage` silently drops path entries for missing directories, so the
  `install -d /opt/tasks` has to stay ahead of the `.pth` write; the `-I` on the verification commands
  keeps the working directory and `PYTHONPATH` off `sys.path`, so the negative assertions test the
  layout and not whatever happens to sit in `/opt/airflow`. Rebuild with `make rebuild-airflow-image`
  after changing `airflow/requirements.txt`.
- **Three pins in `airflow/requirements.txt` are not ETL dependencies.** `pendulum`,
  `lazy-object-proxy` and `dill` are held at the versions `apache/airflow:2.7.3` ships so values
  pickled by Airflow round-trip through the venv unchanged. They look like cruft in a manifest titled
  "ETL dependencies"; dropping them breaks task I/O at run time.
- **The Airflow version is written in one place** — the `FROM` line in `airflow/Dockerfile`. It used
  to be three; the native `pyproject.toml` pin and the `Makefile` constraints URL both went away with
  the host Airflow venv. Bumping it means revisiting the three pickle pins above.
- **Airflow connections are seeded** by `airflow/scripts/init-airflow.sh`, not defined
  in the DAG.
  `app_pg_conn` (schema `app`) and `api_graphql_conn` are the ones in use — the latter's `host`
  (`http://api:4000`) is passed straight to `RequestsHTTPTransport` as the full URL. `neo4j_conn` and
  `snowflake_conn` are also seeded but nothing references them; there is no Snowflake integration.
- **Host tests never touch a service.** Anything added to `airflow/tests/` stubs Postgres and the API,
  so `make test` runs with nothing started. It also cannot see the image's `.pth` file or the compose
  bind mounts — `make test-runtimes` is what covers that gap, by asking each in-container interpreter
  what it can import.
