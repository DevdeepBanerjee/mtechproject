# Explainable GraphRAG for Precision Agriculture

## Overview
This project implements an Explainable GraphRAG framework for precision agriculture. It combines Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), and a Neo4j Knowledge Graph to answer agricultural questions using scholarly articles and structured agricultural datasets.

## Features
- Knowledge Graph construction using Neo4j
- GraphRAG-based question answering
- Explainable answer generation
- Semantic document retrieval
- Agricultural domain knowledge integration
- Natural language query support

## Technologies Used
- Python
- Neo4j
- Streamlit
- LangChain
- OpenAI API
- FAISS
- Pandas
- NetworkX

## Project Structure
```
AGRICULTURE PROJECT/
├── data/
├── app.py
├── main.py
├── extractor.py
├── chunker.py
├── normalizer.py
├── neo4j_writer.py
├── config.py
└── requirements.txt
```

## Installation

```bash
git clone https://github.com/your-username/explainable-graphrag-agriculture.git
cd explainable-graphrag-agriculture
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Example Questions

- What are the symptoms of rice blast disease?
- Which pesticide is recommended for stem borer?
- What crops are suitable for West Bengal?
- What happens if stem borer is not controlled?

## Future Work

- Multi-language support
- Larger agricultural knowledge graphs
- Improved explainability
- Integration with real-time agricultural data

## Authors

Devdeep Banerjee

M.Tech, Dr. B. C. Roy Engineering College

## License

This project is intended for academic and research purposes.
