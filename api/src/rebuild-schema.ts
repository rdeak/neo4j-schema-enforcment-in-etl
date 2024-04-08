import { ApolloServer } from "@apollo/server";
import { startStandaloneServer } from "@apollo/server/standalone";
import { Neo4jGraphQL } from "@neo4j/graphql";
import { toGraphQLTypeDefs } from "@neo4j/introspector";
import neo4j from "neo4j-driver";
import { driver } from "./neo4jDriver.js";

const sessionFactory = () =>
  driver.session({ defaultAccessMode: neo4j.session.READ });

// We create a async function here until "top level await" has landed
// so we can use async/await
async function main() {
  const readonly = true; // We don't want to expose mutations in this case
  const typeDefs = await toGraphQLTypeDefs(sessionFactory, readonly);

  const neoSchema = new Neo4jGraphQL({ typeDefs, driver });

  const server = new ApolloServer({
    schema: await neoSchema.getSchema(),
  });

  await startStandaloneServer(server, {
    context: async ({ req }) => ({ req }),
  });
}

await main();
