"""Read invoices out of Postgres, pre-shaped as GraphQL ``InvoiceCreateInput``."""

import logging

import pandas as pd
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)

INVOICES_SQL = """
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


def extract_invoices(pg_uri: str) -> list:
    try:
        engine = create_engine(pg_uri)

        logger.info("Extracting invoices from PostgreSQL")
        df = pd.read_sql(sql=INVOICES_SQL, con=engine)

        logger.info(f"Extracted {len(df)} invoices from PostgreSQL")
        return df.to_dict("records")

    except Exception as e:
        logger.error(f"Failed to extract invoices: {str(e)}")
        raise
