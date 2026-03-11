# Refactoring

## Usage of GraphDB Arangodb
1. For the future, we do not want to store rules in JSON or ChromaDB. Instead, we want to store them in a graph database Arangodb. This will allow us to have more complex relationships between rules, conditions, and actions, and will also make it easier to query and update the rules.
2. Arangodb will allow us to store rules as nodes and their relationships (e.g., "triggers", "depends on", "conflicts with") as edges. This will enable more sophisticated reasoning and planning capabilities, as the agent can traverse the graph to find relevant rules and their connections.
3. We will need to refactor the reasoning tool to query Arangodb instead of JSON files and ChromaDB. This will involve writing new database access code and updating the logic for retrieving
and filtering rules based on the observations and keywords.
4. We will also need to update the storage design in the architect-llm-reasoning skill to include the new graph database schema and how it will be used for storing knowledge, planning strategies, and capabilities.
5. Arangodb is accessible via port 8529 on this host, so we will need to ensure that our MCP server can connect to it and that the necessary credentials and connection details are securely stored and accessed. Make the connection details configurable in the MCP server configuration.
6. We would like to do embeddings via the existing embedding model. Embeddings should be applied to nodes in the graph database to enable semantic search capabilities. We will need to implement a mechanism to generate and store embeddings for the rules in Arangodb, and update the reasoning tool to utilize these embeddings for semantic retrieval. The embeddings should be a part of the json structure of the nodes in Arangodb, allowing for efficient retrieval based on semantic similarity.
7. Same goes for edges, we want to have embeddings for edges as well, so that we can do semantic search not only on the nodes (rules) but also on the relationships between them. This will allow for more nuanced reasoning and planning based on the connections between rules.

## Task
1. Refactor the reasoning tool to query Arangodb instead of JSON files and ChromaDB.
2. Update the architect-llm-reasoning skill to include the new graph database schema and how it will be used for storing knowledge, planning strategies, and capabilities.
3. Implement a mechanism to generate and store embeddings for the rules in Arangodb, and update the reasoning tool to utilize these embeddings for semantic retrieval.
4. Implement a mechanism to generate and store embeddings for the edges in Arangodb, and update the reasoning tool to utilize these embeddings for semantic retrieval based on relationships between rules.
5. Ensure that the MCP server can connect to Arangodb and that the necessary credentials and connection details are securely stored and accessed.
6. The database can be configured via the mcp server configuration, allowing for flexibility in deployment environments. Password and username should be stored securely, for example via environment variables or a secrets manager, and not hardcoded in the codebase.
7. Update documentation to reflect the new architecture and usage of Arangodb for rule storage and retrieval. This includes updating the reasoning tool architecture documentation, the architect-llm-reasoning skill documentation, and any relevant user guides or developer documentation as well as the requirements md-files and the corresponding acceptance criteria to reflect the new storage and retrieval mechanisms.