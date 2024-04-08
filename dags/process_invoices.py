from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import pandas as pd
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from sqlalchemy import create_engine
from airflow.models import Variable
import json


def load_invoices_from_pg(**kwargs):
    db_conn_uri = Variable.get("pg_conn")
    engine = create_engine(db_conn_uri)

    query = """
        SELECT 
        i.id, 
        i.issue_date, 
        i.pos, 
        json_build_object(
            'create', json_agg(
                json_build_object(
                    'node', json_build_object(
                        'invoiceNo', i.id::text, 
                        'price', ii.price, 
                        'quantity', ii.quantity
                    )
                )
            )
        ) AS items
        FROM invoices i
        JOIN invoice_items ii ON i.id = ii.invoice_id
        GROUP BY i.id
    """

    df = pd.read_sql(query, engine)
    kwargs['ti'].xcom_push(key='invoice_data', value=df.to_json(orient='records'))


def save_invoices_to_neo4j(**kwargs):
    # TODO move to Airflow connection
    transport = RequestsHTTPTransport(url='http://localhost:4000', use_json=True)
    client = Client(transport=transport, fetch_schema_from_transport=True)

    mutation = gql("""
            mutation CreateInvoices($input: [InvoiceCreateInput!]!) {
                createInvoices(input: $input) {
                    invoices {
                        no
                        pos
                        issued
                        items {
                            invoiceNo
                            price
                            quantity
                        }
                    }
                }
            }
        """)

    ti = kwargs['ti']
    data_json = ti.xcom_pull(key='invoice_data', task_ids='fetch_data_from_db')
    data = json.loads(data_json)

    for row in data:
        input = {
            "no": str(row["id"]),
            "issued": row["issue_date"].strftime("%Y-%m-%d"),
            "pos": row["pos"],
            "items": row["items"]
        }
        params = {"input": input}
        result = client.execute(mutation, variable_values=params)
        print(result)


with DAG(
        dag_id='process_invoices',
        description="Dummy DAG used for POC",
        tags=["ETL", "PG-NEO4J"],
        schedule_interval=timedelta(days=1),
        start_date=days_ago(1),
        catchup=False
) as dag:
    fetch_data_from_db_task = PythonOperator(
        task_id='fetch_data_from_db',
        python_callable=load_invoices_from_pg,
        provide_context=True,
    )

    send_to_graphql_api_task = PythonOperator(
        task_id='send_to_graphql_api',
        python_callable=save_invoices_to_neo4j,
        provide_context=True,
    )

    fetch_data_from_db_task >> send_to_graphql_api_task
