# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A demonstration that a Neo4j schema, expressed as GraphQL type definitions and enforced as database
constraints, is what stops an ETL pipeline from writing duplicates — not the pipeline itself. Postgres
holds the source invoices, Airflow extracts them, and the only write path into Neo4j is the GraphQL API.

## Commands

Everything runs through Docker Compose; `make help` lists the targets.

| Command | What it does |
|---|---|
| `make up` | `docker compose up -d` — starts Neo4j, Postgres, the API, and Airflow |
| `make clean` | Tears down containers, volumes, and images |
| `make dev` | Host-side dev setup: pnpm install in `api/`, venv + pip in `airflow/` |
| `make rebuild-api-image` | Rebuild + recreate only the `api` service |
| `make rebuild-airflow-image` | Rebuild the shared Airflow image, recreate init/webserver/scheduler |

In `api/` (Node 20 via `.nvmrc`, pnpm):

- `pnpm dev` — runs `tsc --watch` and `node --watch dist/index.js` concurrently (this is also the
  container's `CMD`; the `api` service is a dev container, not a production build)
- `pnpm build` — `tsc` to `dist/`
- `pnpm rebuild-schema` — see "Two API entry points" below

There are **no tests and no lint script**. Prettier is a devDependency with no npm script; invoke it as
`pnpm exec prettier`. Don't invent test commands.

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

**The DAG (`airflow/dags/process_invoices.py`)** has two tasks. `extract_invoices` runs one SQL query
that pre-shapes each row into the exact nested `InvoiceCreateInput` shape (the `json_build_object(...)`
with a `create`/`node` structure is GraphQL input, not a Postgres convention). `load_to_neo4j` then
loops the rows through the auto-generated `createInvoices` mutation over HTTP.

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
  creates it; the API selects it via `NEO4J_BASE`. In Neo4j Browser
  (http://localhost:7474/browser/?db=data) you must switch databases or your Cypher hits an empty graph.
- **`InvoiceItem` carries two labels**: `@node(labels: ["InvoiceItem", "PGInvoice"])`. Hand-written
  Cypher matching only `:InvoiceItem` still works, but the stored nodes have both.
- **Two API entry points.** `index.ts` serves the hand-written SDL on port 4000. `rebuild-schema.ts`
  (`pnpm rebuild-schema`) is a one-off that introspects the *live* graph with `@neo4j/introspector` in
  readonly mode and serves the result — despite the name it writes nothing to disk, so it is not a
  codegen step for `api/graphql/`.
- **Two Neo4j hosts.** `api/.env` points at `bolt://localhost:7687` for running the API on the host;
  compose overrides `NEO4J_HOST` to `bolt://neo4j:7687` inside the network.
- **Airflow connections are seeded** by `airflow/scripts/init-airflow.sh`, not defined in the DAG.
  `app_pg_conn` (schema `app`) and `api_graphql_conn` are the ones in use — the latter's `host`
  (`http://api:4000`) is passed straight to `RequestsHTTPTransport` as the full URL. `neo4j_conn` and
  `snowflake_conn` are also seeded but nothing references them; there is no Snowflake integration.
- **The README's Postgres row is stale.** It lists `etl_user` / `etl_password` / database `data`; the
  real values from `docker-compose.yml` are `airflow` / `airflow`, with the invoice tables in database
  `app`. The Airflow, API, and Neo4j rows are accurate.
