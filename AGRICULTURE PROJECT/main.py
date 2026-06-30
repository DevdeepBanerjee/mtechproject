from pathlib import Path

from xml_parser import XMLParser
from chunker import SemanticChunker
from extractor import AgricultureExtractor
from normalizer import GraphNormalizer
from neo4j_writer import Neo4jWriter


def main():

    parser = XMLParser()

    chunker = SemanticChunker()

    extractor = AgricultureExtractor()

    normalizer = GraphNormalizer()

    writer = Neo4jWriter()

    data_folder = Path("data")

    xml_files = list(data_folder.glob("*.xml"))

    print(f"\nFound {len(xml_files)} XML files.\n")

    for index, xml_file in enumerate(xml_files):

        print("=" * 80)

        print(f"[{index+1}/{len(xml_files)}] Processing : {xml_file.name}")

        try:

            document = parser.parse_xml(xml_file)

            chunks = chunker.chunk_document(document)

            extracted = extractor.extract_document(chunks)

            normalized = normalizer.normalize(extracted)

            writer.write_graph(normalized)

            print("Completed Successfully\n")

        except Exception as e:

            print(f"Error : {e}")

    writer.close()

    print("\nKnowledge Graph Construction Completed.")


if __name__ == "__main__":

    main()