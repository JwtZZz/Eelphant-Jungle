# Elephant Jungle

This project now runs in two parts:

- `frontend/` contains the React + Vite client.
- `backend/` contains the FastAPI + RAG backend.
- `pixexport/` contains the sprite assets used by the UI.

## Run

### Backend

```powershell
cd "D:\elephant jungle\backend"
.\.venv\Scripts\Activate.ps1
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```powershell
cd "D:\elephant jungle\frontend"
npm install
npm run dev
```

Open:

- `http://127.0.0.1:5500`

## Structure

- `backend/.env` stores local API keys and is not committed.
- `backend/rag.db` stores local metadata and is not committed.
- `backend/chroma/` stores the local vector index and is not committed.

## Notes

- `frontend/public/sheet.png` is the sprite sheet used by the chat runner.
- The frontend expects the backend API to be available on port `8000` of the same host.
