from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# Folder containing evidence documents
EVIDENCE_FOLDER = Path("evidence")

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Create persistent ChromaDB database
client = chromadb.PersistentClient(path="chroma_db")

# Create collection
collection = client.get_or_create_collection(
    name="investigation_evidence"
)


def load_documents():
    """
    Reads every .txt file inside evidence/
    """

    documents = []

    for file in EVIDENCE_FOLDER.glob("*.txt"):

        with open(file, "r", encoding="utf-8") as f:

            documents.append({
                "id": file.stem,
                "filename": file.name,
                "content": f.read()
            })

    return documents


def build_vector_database():
    """
    Reads all evidence files and stores them in ChromaDB.
    Only indexes once.
    """

    if collection.count() > 0:
        return

    documents = load_documents()

    for doc in documents:

        embedding = model.encode(doc["content"]).tolist()

        collection.add(
            ids=[doc["id"]],
            documents=[doc["content"]],
            embeddings=[embedding],
            metadatas=[
                {
                    "filename": doc["filename"]
                }
            ]
        )


def retrieve_documents(query, top_k=3):
    """
    Returns the most relevant evidence documents.
    """

    query_embedding = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    return results