from neo4j import GraphDatabase

from config import (
    NEO4J_USERNAME,
    NEO4J_PASSWORD
)


class Neo4jWriter:

    def __init__(self):

        self.driver = GraphDatabase.driver(
            "bolt+ssc://p-mt-2a41353b6b9a-1-0090.production-orch-0695.neo4j.io:7687",
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

        self.database = "f9c5be28"

    def close(self):

        self.driver.close()

    def create_entity(self, tx, entity):

        label = entity["type"].strip().replace(" ", "_")

        query = "MERGE (n:" + "`" + label + "`" + " {name: $name})"

        tx.run(query, name=entity["name"])

    def write_entities(self, entities):

        with self.driver.session(database=self.database) as session:

            for entity in entities:

                try:
                    session.execute_write(self.create_entity, entity)
                except Exception as e:
                    print(f"Entity error ({entity}): {e}")

    def create_relationship(self, tx, relationship):

        relation = relationship["relation"].strip().replace(" ", "_").upper()

        query = (
            "MATCH (a {name: $source}) "
            "MATCH (b {name: $target}) "
            "MERGE (a)-[r:" + "`" + relation + "`" + "]->(b)"
        )

        tx.run(query, source=relationship["source"], target=relationship["target"])

    def write_relationships(self, relationships):

        with self.driver.session(database=self.database) as session:

            for relationship in relationships:

                try:
                    session.execute_write(self.create_relationship, relationship)
                except Exception as e:
                    print(f"Relationship error ({relationship}): {e}")

    def write_graph(self, data):

        entities = data.get("entities", [])
        relationships = data.get("relationships", [])

        print(f"Inserting {len(entities)} entities...")
        self.write_entities(entities)

        print(f"Inserting {len(relationships)} relationships...")
        self.write_relationships(relationships)

        print("Graph successfully stored in Neo4j.")