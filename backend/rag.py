from providers import embed_texts, generate_answer, generate_general_answer
from store import insert_chunks, insert_document, search_chunks


CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
DEFAULT_TOP_K = 5
FALLBACK_SCORE_THRESHOLD = 0.35


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be larger than overlap")

    chunks: list[str] = []
    step = chunk_size - overlap
    i = 0
    while i < len(clean):
        chunks.append(clean[i : i + chunk_size])
        i += step
    return chunks


def ingest_document(source: str, content: str) -> dict:
    doc_id = insert_document(source=source, content=content)
    chunks = chunk_text(content)
    if not chunks:
        return {"document_id": doc_id, "chunks": 0}
    embeddings = embed_texts(chunks)
    count = insert_chunks(document_id=doc_id, chunks=chunks, embeddings=embeddings)
    return {"document_id": doc_id, "chunks": count}


def search(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    query_vector = embed_texts([query])[0]
    return search_chunks(query_embedding=query_vector, top_k=top_k)


def chat(query: str, top_k: int = DEFAULT_TOP_K) -> dict:
    hits = search(query=query, top_k=top_k)
    contexts = [h["content"] for h in hits]
    top_score = hits[0]["score"] if hits else -1.0

    if top_score < FALLBACK_SCORE_THRESHOLD:
        answer = generate_general_answer(query=query)
        return {"answer": answer, "contexts": hits, "mode": "general"}

    answer = generate_answer(query=query, contexts=contexts)
    return {"answer": answer, "contexts": hits, "mode": "rag"}
