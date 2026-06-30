from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
)

print("URI:", NEO4J_URI)
print("USER:", NEO4J_USERNAME)
print()

try:
    driver.verify_connectivity()
    print("✅ Neo4j Connected Successfully!")

    with driver.session() as session:
        result = session.run("RETURN 1 AS test")
        print("Test query result:", result.single()["test"])

except Exception as e:
    print("❌ Connection Error:")
    print(e)

finally:
    driver.close()