# ETL sample

An example of enforcing a Neo4j schema from inside an ETL process, using a GraphQL API
as the only write path.

```
Postgres (db `app`)  ──▶  Airflow DAG  ──▶  GraphQL API  ──▶  Neo4j (db `data`)
   source of truth       process_invoices   Apollo + @neo4j/graphql
```

The API is schema-first: `api/graphql/invoice.graphql` declares `Invoice.id` as `@unique`, and
`assertIndexesAndConstraints({ create: true })` turns that directive into a real Neo4j
constraint at boot. The DAG has three tasks and no idempotency logic — it calls the
generated `createInvoices` mutation, a plain create.

So the first run loads cleanly and **every rerun fails on the constraint**. That is the
point of the sample: the thing that refuses duplicate data is the schema, not the
pipeline.

## Prerequisites

1. nvm
2. [uv](https://docs.astral.sh/uv/) — fetches the Python interpreter for the ETL venv, so no system Python needed
3. docker
4. docker-compose
5. Make

## Getting started

```bash
make up     # Neo4j, Postgres, the API and Airflow
```

The `process_invoices` DAG is created paused. Unpause or trigger it from the Airflow UI
at http://localhost:8080 before anything moves. Run it twice to see the constraint reject
the second load.

List of available commands:

| Command                    | Description                                      |
|----------------------------|--------------------------------------------------|
| make up                    | Starts all services                              |
| make clean                 | Clean all Docker assets created by `up` command  |
| make rebuild-api-image     | Rebuilds Docker image used by API                |
| make rebuild-airflow-image | Rebuilds Docker image used by AirFlow            |
| make dev                   | Install all dev dependencies                     |
| make dev-api               | API dev environment only                         |
| make dev-airflow           | ETL venv (`airflow/.venv`, Python 3.11)          |
| make test                  | Run the ETL task tests                           |
| make test-runtimes         | Verify the source roots inside the running image |

Two notes on the dev targets. `make dev-airflow` builds the ETL interpreter's venv, which
has **no Airflow in it** — see below — so Airflow imports in `airflow/dags/` are expected
to show up unresolved in your editor. And `airflow/tests/` has nothing in it yet, so
`make test` passes without running anything.

## Airflow runs on two interpreters

The Airflow image and the pipeline code want different Pythons and different
dependency trees, so `airflow/` builds both into one image and splits its files
by which one runs them:

| Directory | Python | Airflow | Runs |
|---|---|---|---|
| `airflow/dags/` | 3.8, the image's own | installed | scheduler, webserver, DAG parsing, plain `@task` |
| `airflow/tasks/` | 3.11 (`$ETL_PYTHON`) | **not installed** | every `@isolated_task` body |

There is **one manifest** — the 3.11 side's `airflow/requirements.txt`, which
`airflow/pyproject.toml` references — because the
base image already is the manifest for the other, and Airflow's own execution of
`ExternalPythonOperator` isn't something a host venv reproduces. Neither
interpreter can import the other's code, and the image build fails if that stops
being true. **[airflow/README.md](airflow/README.md) explains the whole thing**:
how a task crosses the boundary, what enforces it, and how to point your IDE at
it.

## Service dictionary

| Service                           | Host                                   | User    | Pass     | Database |
|-----------------------------------|----------------------------------------|---------|----------|----------|
| Airflow                           | http://localhost:8080                  | airflow | airflow  |          |
| Graphql API (interface for Neo4J) | http://localhost:4000                  |         |          |          |
| Postgres (data source)            | localhost:5432                         | airflow | airflow  | app      |
| Neo4j (use `data` database)       | http://localhost:7474/browser/?db=data | neo4j   | password | data     |

## Useful links

* [Neo4j Graphql Toolbox](https://graphql-toolbox.neo4j.io/)
* [Custom Scalars](https://neo4j.com/docs/graphql/current/type-definitions/types/)

## Licence

MIT
