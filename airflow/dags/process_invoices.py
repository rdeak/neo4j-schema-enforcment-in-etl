from __future__ import annotations

from airflow.decorators import dag, task
from datetime import datetime, timedelta
import logging

from isolated_task import isolated_task

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
        import logging
        import pandas as pd
        from sqlalchemy import create_engine

        logger = logging.getLogger(__name__)

        try:
            query = """
                SELECT
                    i.id,
                    i.issue_date::text as issue_date,
                    i.pos,
                    json_build_object(
                            'create', json_agg(
                            json_build_object(
                                    'node', json_build_object(
                                    'itemId', ii.id::text,
                                    'invoiceId', i.id::text,
                                    'price', ii.price,
                                    'quantity', ii.quantity
                                            )
                            )
                                      )
                    ) AS items
                FROM invoices i
                         JOIN invoice_items ii ON i.id = ii.invoice_id
                GROUP BY i.id
                ORDER BY i.id
            """

            engine = create_engine(conn["pg_uri"])

            logger.info("Extracting invoices from PostgreSQL")
            df = pd.read_sql(sql=query, con=engine)

            logger.info(f"Extracted {len(df)} invoices from PostgreSQL")
            return df.to_dict('records')

        except Exception as e:
            logger.error(f"Failed to extract invoices: {str(e)}")
            raise

    @isolated_task
    def load_to_neo4j(conn: dict, invoices: list[dict]) -> dict:
        import logging
        from gql import Client, gql
        from gql.transport.requests import RequestsHTTPTransport

        logger = logging.getLogger(__name__)

        if not invoices:
            logger.info("No invoices to process")
            return {"processed": 0, "failed": 0}

        try:
            transport = RequestsHTTPTransport(
                url=conn["api_url"],
                use_json=True,
            )
            client = Client(transport=transport, fetch_schema_from_transport=True)

            mutation = gql("""
                mutation CreateInvoices($input: [InvoiceCreateInput!]!) {
                    createInvoices(input: $input) {
                        invoices {
                            id
                            pos
                            issued
                        }
                    }
                }
            """)

            for invoice in invoices:
                logger.info(f"Processing invoice: {invoice}")
                input = {
                    "id": str(invoice["id"]),
                    "issued": invoice["issue_date"],
                    "pos": invoice["pos"],
                    "items": invoice["items"]
                }
                params = {"input": input}
                result = client.execute(mutation, variable_values=params)
                logger.info(result)

            logger.info(f"Load complete: {len(invoices)}")
            return {"processed": len(invoices), "failed": 0}

        except Exception as e:
            logger.error(f"Failed to load invoices: {str(e)}")
            raise

    conn = resolve_connections()
    invoices = extract_invoices(conn)
    load_to_neo4j(conn, invoices)


dag_instance = process_invoices_dag()
