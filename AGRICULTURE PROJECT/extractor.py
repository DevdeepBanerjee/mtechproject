import json

from openai import OpenAI

from config import OPENAI_API_KEY


client = OpenAI(
    api_key=OPENAI_API_KEY
)


SYSTEM_PROMPT = """
You are an Agriculture Knowledge Graph Extraction System.

Extract ONLY agriculture knowledge.

Allowed Entity Types:

Crop
Disease
Pest
Pesticide
Fertilizer
Soil
Season
Location
State
District
Country
Weather
Irrigation
Nutrient
FarmerPractice

Allowed Relationships

AFFECTED_BY
CONTROLLED_BY
GROWN_IN
GROWN_DURING
REQUIRES
DEPENDS_ON
HAS_SYMPTOM
CAUSES
PREVENTED_BY

Rules

Return ONLY JSON.

Never explain.

Never write markdown.

Never invent information.

Use only information explicitly mentioned.

Output format

{
 "entities":[
   {
      "name":"",
      "type":""
   }
 ],
 "relationships":[
   {
      "source":"",
      "relation":"",
      "target":""
   }
 ]
}
"""


class AgricultureExtractor:

    def __init__(self):

        self.model = "gpt-4o-mini"

    def call_llm(self, text):

        user_prompt = f"""Extract all agriculture entities and relationships from the following text:

{text}
"""

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=0
        )

        return response.choices[0].message.content

    def extract_chunk(self, chunk):

        try:

            result = self.call_llm(chunk)

            data = json.loads(result)

            if "entities" not in data:
                data["entities"] = []

            if "relationships" not in data:
                data["relationships"] = []

            return data

        except Exception as e:

            print(f"Extraction Error : {e}")

            return {
                "entities": [],
                "relationships": []
            }

    def extract_document(self, chunks):
        """
        Extract entities and relationships from all chunks
        and merge the results.
        """

        all_entities = []
        all_relationships = []

        for index, chunk in enumerate(chunks):

            print(f"Processing Chunk {index + 1}/{len(chunks)}")

            result = self.extract_chunk(chunk)

            all_entities.extend(result.get("entities", []))
            all_relationships.extend(result.get("relationships", []))

        return {
            "entities": all_entities,
            "relationships": all_relationships
        }


if __name__ == "__main__":

    from pathlib import Path

    from xml_parser import XMLParser
    from chunker import SemanticChunker

    parser = XMLParser()
    chunker = SemanticChunker()
    extractor = AgricultureExtractor()

    xml_folder = Path("data")

    for xml_file in xml_folder.glob("*.xml"):

        print(f"\nProcessing: {xml_file.name}")

        document = parser.parse_xml(xml_file)

        chunks = chunker.chunk_document(document)

        output = extractor.extract_document(chunks)

        print(output)