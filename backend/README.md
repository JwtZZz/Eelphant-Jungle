# Minimal RAG Backend

## 1) Install

```bash
pip install -r requirements.txt
```

## 2) Configure

Copy `.env.example` to `.env` and set:

- `DASHSCOPE_API_KEY`
- `MINIMAX_API_KEY`

Service startup auto-loads `backend/.env`.
Optional model/url overrides are in `.env.example`.
Local secrets and local data are intentionally not committed:

- `backend/.env`
- `backend/rag.db`
- `backend/chroma/`

## 3) Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 4) APIs

- `POST /ingest`
  - body:
```json
{"source":"manual","content":"your document text"}
```

- `POST /search`
  - body:
```json
{"query":"what is ...","top_k":5}
```

- `POST /chat`
  - body:
```json
{"query":"ask with rag","top_k":5}
```

`/chat` now prefers RAG results and falls back to general chat when retrieval confidence is low.
Embeddings are now indexed in Chroma, while SQLite keeps document and chunk metadata.
