from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.hooks.base import BaseHook
from datetime import datetime, timedelta
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
import logging
import pandas as pd

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
    def extract_invoices() -> list[dict]:
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

            pg_hook = PostgresHook(postgres_conn_id="app_pg_conn")

            logger.info("Extracting invoices from PostgreSQL")
            df = pg_hook.get_pandas_df(sql=query)

            logger.info(f"Extracted {len(df)} invoices from PostgreSQL")
            return df.to_dict('records')

        except Exception as e:
            logger.error(f"Failed to extract invoices: {str(e)}")
            raise

    @task
    def load_to_neo4j(invoices: list[dict]) -> dict:
        if not invoices:
            logger.info("No invoices to process")
            return {"processed": 0, "failed": 0}

        try:
            graphql_conn = BaseHook.get_connection('api_graphql_conn')

            transport = RequestsHTTPTransport(
                url=graphql_conn.host,
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


        except Exception as e:
            logger.error(f"Failed to load invoices: {str(e)}")
            raise

    invoices = extract_invoices()
    load_to_neo4j(invoices)


dag_instance = process_invoices_dag()