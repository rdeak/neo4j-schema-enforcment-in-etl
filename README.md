# ETL sample

This repo contains example how enforce Neo4j database schema within ETL process using Graphql API.

API contain plain simple CRUD interface for Neo4j database.
ETL is handled by AirFlow simple single DAG with two plain tasks.
The goal is just to show how data flow, API and ETL process do not handle duplicated data.

## Prerequisites

1. nvm
2. python 3.11
3. docker
4. docker-compose
5. Make

## Getting started

List of available commands:

| Command                    | Description                                     |
|----------------------------|-------------------------------------------------|
| make up                    | Starts all services                             |
| make clean                 | Clean all Docker assets created by `up` command |
| make rebuild-api-image     | Rebuilds Docker image used by API               |
| make rebuild-airflow-image | Rebuilds Docker image used by AirFlow           |
| make dev                   | Install all dev dependencies                    |

## Service dictionary

| Service                           | Host                                   | User     | Pass         | Database |
|-----------------------------------|----------------------------------------|----------|--------------|----------|
| Airflow                           | http://localhost:8080                  | airflow  | airflow      |          |
| Graphql API (interface for Neo4J) | http://localhost:4000                  |          |              |          |
| Postgres (data source)            | localhost                              | etl_user | etl_password | data     |
| Neo4j (use `data` database)       | http://localhost:7474/browser/?db=data | neo4j    | password     | data     |

## Useful links

* [Neo4j Graphql Toolbox](https://graphql-toolbox.neo4j.io/)
* [Custom Scalars](https://neo4j.com/docs/graphql/current/type-definitions/types/)

## Licence

MIT
