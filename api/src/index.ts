import { ApolloServer } from "@apollo/server";
import { startStandaloneServer } from "@apollo/server/standalone";
import { loadFiles } from "@graphql-tools/load-files";
import { Neo4jGraphQL } from "@neo4j/graphql";
import { driver } from "./neo4jDriver.js";

const typeDefs = await loadFiles("graphql/**/*.graphql");

const neoSchema = new Neo4jGraphQL({ typeDefs, driver });
const schema = await neoSchema.getSchema();
await neoSchema.checkNeo4jCompat();
await neoSchema.assertIndexesAndConstraints({ options: { create: true } });

const server = new ApolloServer({
  schema,
});

const { url } = await startStandaloneServer(server, {
  listen: { port: 4000 },
  context: async ({ req }) => ({
    req,
    sessionConfig: { database: process.env.NEO4J_BASE },
  }),
});

console.log(`🚀 Server ready at ${url}`);
