from __future__ import annotations

from datetime import datetime, timedelta
import logging

from airflow.decorators import dag, task

from operators.isolated_task import isolated_task

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'data_team',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': False,
    'email_on_retry': False,
}


@dag(
    dag_id='process_invoices',
    description="ETL pipeline: PostgreSQL invoices to Neo4j via GraphQL",
    tags=["ETL", "PG-NEO4J"],
    schedule='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    max_active_runs=1,
)
def process_invoices_dag():

    @task
    def resolve_connections() -> dict:
        from airflow.hooks.base import BaseHook
        from airflow.providers.postgres.hooks.postgres import PostgresHook

        return {
            "pg_uri": PostgresHook(postgres_conn_id="app_pg_conn").get_uri(),
            "api_url": BaseHook.get_connection("api_graphql_conn").host,
        }

    @isolated_task
    def extract_invoices(conn: dict) -> list[dict]:
        from tasks.extract import extract_invoices as run_extract

        return run_extract(conn["pg_uri"])

    @isolated_task
    def load_to_neo4j(conn: dict, invoices: list[dict]) -> dict:
        from tasks.load import load_invoices

        return load_invoices(conn["api_url"], invoices)

    conn = resolve_connections()
    invoices = extract_invoices(conn)
    load_to_neo4j(conn, invoices)


dag_instance = process_invoices_dag()
