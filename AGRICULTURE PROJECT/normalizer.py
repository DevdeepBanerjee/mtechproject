class GraphNormalizer:

    def __init__(self):
        pass

    def normalize_name(self, name):
        """
        Normalize entity names.
        """

        if not name:
            return ""

        return " ".join(name.strip().split()).title()

    def normalize_entities(self, entities):

        unique = {}

        for entity in entities:

            name = self.normalize_name(entity.get("name", ""))

            entity_type = entity.get("type", "").strip()

            if not name or not entity_type:
                continue

            key = (entity_type, name)

            unique[key] = {
                "name": name,
                "type": entity_type
            }

        return list(unique.values())

    def normalize_relationships(self, relationships):

        unique = {}

        for rel in relationships:

            source = self.normalize_name(rel.get("source", ""))

            target = self.normalize_name(rel.get("target", ""))

            relation = rel.get("relation", "").strip().upper()

            if not source or not target or not relation:
                continue

            key = (
                source,
                relation,
                target
            )

            unique[key] = {
                "source": source,
                "relation": relation,
                "target": target
            }

        return list(unique.values())

    def normalize(self, data):

        entities = self.normalize_entities(
            data.get("entities", [])
        )

        relationships = self.normalize_relationships(
            data.get("relationships", [])
        )

        return {
            "entities": entities,
            "relationships": relationships
        }


if __name__ == "__main__":

    sample = {

        "entities": [

            {"name": "rice", "type": "Crop"},
            {"name": "Rice", "type": "Crop"},
            {"name": "RICE", "type": "Crop"}

        ],

        "relationships": [

            {
                "source": "rice",
                "relation": "grown_in",
                "target": "india"
            },

            {
                "source": "Rice",
                "relation": "GROWN_IN",
                "target": "India"
            }

        ]
    }

    normalizer = GraphNormalizer()

    output = normalizer.normalize(sample)

    print(output)