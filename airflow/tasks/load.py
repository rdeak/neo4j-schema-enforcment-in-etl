import logging

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

logger = logging.getLogger(__name__)

CREATE_INVOICES = """
    mutation CreateInvoices($input: [InvoiceCreateInput!]!) {
        createInvoices(input: $input) {
            invoices {
                id
                pos
                issued
            }
        }
    }
"""


def as_create_input(invoice: dict) -> dict:
    return {
        "id": str(invoice["id"]),
        "issued": invoice["issue_date"],
        "pos": invoice["pos"],
        "items": invoice["items"],
    }


def load_invoices(api_url: str, invoices: list) -> dict:
    if not invoices:
        logger.info("No invoices to process")
        return {"processed": 0, "failed": 0}

    try:
        transport = RequestsHTTPTransport(
            url=api_url,
            use_json=True,
        )
        client = Client(transport=transport, fetch_schema_from_transport=True)
        mutation = gql(CREATE_INVOICES)

        for invoice in invoices:
            logger.info(f"Processing invoice: {invoice}")
            params = {"input": as_create_input(invoice)}
            result = client.execute(mutation, variable_values=params)
            logger.info(result)

        logger.info(f"Load complete: {len(invoices)}")
        return {"processed": len(invoices), "failed": 0}

    except Exception as e:
        logger.error(f"Failed to load invoices: {str(e)}")
        raise
