import json
import sqlite3
from pathlib import Path
from typing import Iterable

import chromadb


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "rag.db"
CHROMA_DIR = BASE_DIR / "chroma"
CHROMA_COLLECTION = "rag_chunks"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_chroma_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(document_id) REFERENCES documents(id)
            )
            """
        )


def insert_document(source: str, content: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO documents(source, content) VALUES(?, ?)",
            (source, content),
        )
        return int(cur.lastrowid)


def insert_chunks(document_id: int, chunks: Iterable[str], embeddings: Iterable[list[float]]) -> int:
    chunk_list = list(chunks)
    embedding_list = list(embeddings)
    payload = [
        (document_id, chunk, json.dumps(embedding, ensure_ascii=False))
        for chunk, embedding in zip(chunk_list, embedding_list)
    ]
    with get_conn() as conn:
        before_id = conn.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM chunks").fetchone()["max_id"]
        conn.executemany(
            "INSERT INTO chunks(document_id, content, embedding_json) VALUES(?, ?, ?)",
            payload,
        )
    chunk_ids = [str(before_id + index + 1) for index in range(len(payload))]
    collection = get_chroma_collection()
    collection.upsert(
        ids=chunk_ids,
        documents=chunk_list,
        embeddings=embedding_list,
        metadatas=[{"document_id": document_id} for _ in chunk_list],
    )
    return len(payload)


def load_all_chunks() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, document_id, content, embedding_json FROM chunks ORDER BY id ASC"
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "document_id": int(row["document_id"]),
            "content": row["content"],
            "embedding": json.loads(row["embedding_json"]),
        }
        for row in rows
    ]


def sync_chroma_index() -> int:
    chunks = load_all_chunks()
    if not chunks:
        return 0

    collection = get_chroma_collection()
    collection.upsert(
        ids=[str(chunk["id"]) for chunk in chunks],
        documents=[chunk["content"] for chunk in chunks],
        embeddings=[chunk["embedding"] for chunk in chunks],
        metadatas=[{"document_id": chunk["document_id"]} for chunk in chunks],
    )
    return len(chunks)


def search_chunks(query_embedding: list[float], top_k: int) -> list[dict]:
    collection = get_chroma_collection()
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=max(1, top_k),
    )

    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    distances = result.get("distances", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]

    hits = []
    for chunk_id, content, distance, metadata in zip(ids, documents, distances, metadatas):
        distance_value = float(distance) if distance is not None else 1.0
        score = max(0.0, 1.0 - distance_value)
        hits.append(
            {
                "chunk_id": int(chunk_id),
                "document_id": int((metadata or {}).get("document_id", 0)),
                "content": content,
                "score": score,
                "distance": distance_value,
            }
        )
    return hits
