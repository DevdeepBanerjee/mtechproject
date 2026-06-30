from neo4j import GraphDatabase
from config import NEO4J_USERNAME, NEO4J_PASSWORD

driver = GraphDatabase.driver(
    "bolt+ssc://p-mt-2a41353b6b9a-1-0090.production-orch-0695.neo4j.io:7687",
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
)

try:
    driver.verify_connectivity()
    print("Connected Successfully!")

    with driver.session(database="f9c5be28") as session:
        result = session.run("RETURN 1 AS test")
        print("Test query result:", result.single()["test"])

except Exception as e:
    print("Error:", e)

finally:
    driver.close()
