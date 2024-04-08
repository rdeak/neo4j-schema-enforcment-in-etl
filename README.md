# ETL sample

This repo contains example how enforce neo4j database schema with Graphql API in ETL process.

## Installation

1. `echo -e "AIRFLOW_UID=$(id -u)" > .env`
2. `docker-compose up airflow-init`
3. `docker-compose up`
4. Add `pg_conn` connection for pg service into Connections
5. Create neo4j database (can be done with neo4j browser)
   ```cypher
   :use system;
   create database data
   ``` 
6. Activate nvm ``
7. In `api` directory run
   ```bash 
   pnpm install
   pnpm dev
   ```

To remove all just run
`docker compose down --volumes --rmi all`

## Usage

| Service                           | Host                           | User     | Pass         | Database |
|-----------------------------------|--------------------------------|----------|--------------|----------|
| Airflow                           | http://localhost:8080          | airflow  | airflow      |          |
| Graphql API (interface for Neo4J) | http://localhost:4000          |          |              |          |
| Postgres (data source)            | localhost                      | etl_user | etl_password | data     |
| Neo4j                             | http://localhost:7474/browser/ | neo4j    | password     | data     |

## Useful links

* [Neo4j Graphql Toolbox](https://graphql-toolbox.neo4j.io/)
* [Custom Scalars](https://neo4j.com/docs/graphql/current/type-definitions/types/)

## Licence

MIT
