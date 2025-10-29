#!/bin/bash
set -e

echo "Initializing Airflow database..."
airflow db migrate

echo "Checking for admin user..."
if airflow users list | grep -q "admin"; then
    echo "Admin user already exists, skipping creation"
else
    echo "Creating admin user..."
    airflow users create \
        --username airflow \
        --password airflow \
        --firstname Local \
        --lastname User \
        --role Admin \
        --email admin@local
    echo "Admin user created successfully"
fi

echo "Checking for connections..."
if airflow connections get app_pg_conn 2>/dev/null; then
    echo "Connection 'app_pg_conn' already exists, skipping"
else
    echo "Creating connection 'app_pg_conn'..."
    airflow connections add 'app_pg_conn' \
        --conn-type 'postgres' \
        --conn-host 'postgres' \
        --conn-login 'airflow' \
        --conn-password 'airflow' \
        --conn-port '5432' \
        --conn-schema 'app' \
        --conn-description 'Application database connection'
    echo "Connection created successfully"
fi

echo "Checking for Neo4j connection..."
if airflow connections get neo4j_conn 2>/dev/null; then
    echo "Connection 'neo4j_conn' already exists, skipping"
else
    echo "Creating connection 'neo4j_conn'..."
    airflow connections add 'neo4j_conn' \
        --conn-type 'neo4j' \
        --conn-host 'neo4j' \
        --conn-login 'neo4j' \
        --conn-password 'password' \
        --conn-port '7687' \
        --conn-description 'Neo4j graph database'
    echo "Connection created successfully"
fi

echo "Checking for Snowflake connection..."
if airflow connections get snowflake_conn 2>/dev/null; then
    echo "Connection 'snowflake_conn' already exists, skipping"
else
    echo "Creating connection 'snowflake_conn'..."
    airflow connections add 'snowflake_conn' \
        --conn-type 'snowflake' \
        --conn-login 'myuser' \
        --conn-password 'mypassword' \
        --conn-schema 'PUBLIC' \
        --conn-extra '{
            "account": "xy12345.us-east-1",
            "warehouse": "COMPUTE_WH",
            "database": "MY_DATABASE",
            "region": "us-east-1",
            "role": "ACCOUNTADMIN"
        }' \
        --conn-description 'Snowflake data warehouse'
    echo "Connection created successfully"
fi

echo "Checking for GQL API connection..."
if airflow connections get api_graphql_conn 2>/dev/null; then
    echo "Connection 'api_graphql_conn' already exists, skipping"
else
    echo "Creating connection 'api_graphql_conn'..."
    airflow connections add 'api_graphql_conn' \
        --conn-type 'http' \
        --conn-host 'http://api:4000'  \
        --conn-description 'App GraphQL API'
fi

echo "Airflow initialization complete!"
