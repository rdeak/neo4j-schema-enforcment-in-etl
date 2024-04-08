
CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    issue_date DATE,
    pos TEXT
);

COPY invoices(id, issue_date, pos)
    FROM '/data/invoices.csv'
    WITH (FORMAT csv, HEADER true);

CREATE TABLE invoice_items (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER,
    price FLOAT,
    quantity DECIMAL(10,2),
    constraint invoice_item_fk
        FOREIGN KEY (invoice_id)
        REFERENCES invoices (id)
);

COPY invoice_items(invoice_id, id, price, quantity)
    FROM '/data/invoice-items.csv'
    WITH (FORMAT csv, HEADER true);
