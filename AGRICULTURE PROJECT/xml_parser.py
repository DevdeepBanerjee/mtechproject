from pathlib import Path
from bs4 import BeautifulSoup


class XMLParser:
    def __init__(self):
        self.namespace = {"tei": "http://www.tei-c.org/ns/1.0"}

    def parse_xml(self, xml_file):
        """
        Parse a GROBID TEI XML file and extract metadata + full text.
        """

        xml_file = Path(xml_file)

        with open(xml_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "xml")

        # -----------------------------
        # Title
        # -----------------------------
        title = ""
        title_tag = soup.find("title", {"type": "main"})
        if title_tag:
            title = title_tag.get_text(" ", strip=True)

        # -----------------------------
        # Abstract
        # -----------------------------
        abstract = ""
        abstract_tag = soup.find("abstract")
        if abstract_tag:
            abstract = abstract_tag.get_text(" ", strip=True)

        # -----------------------------
        # Body
        # -----------------------------
        body_text = ""

        body = soup.find("body")
        if body:
            paragraphs = body.find_all("p")
            body_text = "\n".join(
                p.get_text(" ", strip=True)
                for p in paragraphs
                if p.get_text(strip=True)
            )

        return {
            "file_name": xml_file.name,
            "title": title,
            "abstract": abstract,
            "body": body_text
        }


if __name__ == "__main__":

    from pathlib import Path

    parser = XMLParser()

    xml_folder = Path("data")

    xml_files = list(xml_folder.glob("*.xml"))

    if not xml_files:
        print("No XML files found in data/xml")
    else:
        result = parser.parse_xml(xml_files[0])

        print("=" * 80)
        print("FILE")
        print(result["file_name"])

        print("=" * 80)
        print("TITLE")
        print(result["title"])

        print("=" * 80)
        print("ABSTRACT")
        print(result["abstract"])

        print("=" * 80)
        print("BODY")
        print(result["body"][:2000])