from pathlib import Path
import time
from html import unescape
import re
import xml.etree.ElementTree as ET

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from rag import DEFAULT_TOP_K, chat, ingest_document, search
from store import init_db, sync_chroma_index
from providers import validate_provider_env


app = FastAPI(title="Minimal RAG Backend", version="0.1.0")
load_dotenv(Path(__file__).resolve().parent / ".env")
MARKET_CACHE_TTL_SECONDS = 5
market_cache: dict[str, object] = {"timestamp": 0.0, "coins": []}
BRIEFS_CACHE_TTL_SECONDS = 5 * 60 * 60
briefs_cache: dict[str, object] = {"timestamp": 0.0, "payload": {}}
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestRequest(BaseModel):
    source: str = Field(default="manual")
    title: str | None = None
    url: str | None = None
    published_at: str | None = None
    doc_type: str | None = None
    project: str | None = None
    category: str | None = None
    region: str | None = None
    source_type: str | None = None
    language: str | None = None
    summary: str | None = None
    content: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=20)


class ChatRequest(BaseModel):
    query: str
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=20)


def format_market_cap(value: int | float | None) -> str:
    if value is None:
        return "--"
    number = float(value)
    if number >= 1_000_000_000_000:
        return f"${number / 1_000_000_000_000:.2f}T"
    if number >= 1_000_000_000:
        return f"${number / 1_000_000_000:.1f}B"
    if number >= 1_000_000:
        return f"${number / 1_000_000:.1f}M"
    return f"${number:,.0f}"


def format_price(value: int | float | None) -> str:
    if value is None:
        return "--"
    number = float(value)
    if number >= 1000:
        return f"${number:,.2f}"
    if number >= 1:
        return f"${number:,.4f}"
    return f"${number:,.5f}"


def fetch_market_coins() -> list[dict]:
    now = time.time()
    cached_coins = market_cache.get("coins", [])
    cached_at = float(market_cache.get("timestamp", 0.0))
    if cached_coins and (now - cached_at) < MARKET_CACHE_TTL_SECONDS:
        return list(cached_coins)

    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 30,
        "page": 1,
        "sparkline": "true",
        "price_change_percentage": "24h",
    }
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        if cached_coins:
            return list(cached_coins)
        raise

    coins: list[dict] = []
    for item in payload:
        sparkline = ((item.get("sparkline_in_7d") or {}).get("price")) or []
        coins.append(
            {
                "symbol": (item.get("symbol") or "").upper(),
                "name": item.get("name") or "",
                "image": item.get("image") or "",
                "price": format_price(item.get("current_price")),
                "change": float(item.get("price_change_percentage_24h") or 0.0),
                "low": format_price(item.get("low_24h")),
                "high": format_price(item.get("high_24h")),
                "cap": format_market_cap(item.get("market_cap")),
                "spark": [float(point) for point in sparkline[-12:]] if sparkline else [],
            }
        )
    market_cache["timestamp"] = now
    market_cache["coins"] = coins
    return coins


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", unescape(value or "")).strip()


def parse_rss_items(xml_text: str, limit: int = 8) -> list[dict]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
      return []

    items: list[dict] = []
    for item in channel.findall("item")[:limit]:
        title = strip_html(item.findtext("title", default=""))
        link = item.findtext("link", default="").strip()
        pub_date = item.findtext("pubDate", default="").strip()
        description = strip_html(item.findtext("description", default=""))
        source = strip_html(item.findtext("source", default="")) or "Google News"
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "url": link,
                "published_at": pub_date,
                "summary": description,
                "source": source,
            }
        )
    return items


def fetch_market_briefs() -> dict:
    now = time.time()
    cached_payload = briefs_cache.get("payload", {})
    cached_at = float(briefs_cache.get("timestamp", 0.0))
    if cached_payload and (now - cached_at) < BRIEFS_CACHE_TTL_SECONDS:
        return dict(cached_payload)

    feeds = {
        "social": "https://news.google.com/rss/search?q=site:x.com+(bitcoin+OR+ethereum+OR+solana+OR+crypto)+when:1d&hl=en-US&gl=US&ceid=US:en",
        "news": "https://news.google.com/rss/search?q=(bitcoin+OR+ethereum+OR+crypto)+finance+when:1d&hl=en-US&gl=US&ceid=US:en",
    }

    payload: dict[str, list[dict]] = {}
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            for key, url in feeds.items():
                response = client.get(url)
                response.raise_for_status()
                payload[key] = parse_rss_items(response.text, limit=8)
    except Exception:
        if cached_payload:
            return dict(cached_payload)
        raise

    briefs_cache["timestamp"] = now
    briefs_cache["payload"] = payload
    return payload


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    sync_chroma_index()
    validate_provider_env()


@app.get("/health")
def health() -> dict:
    return {"ok": True, "providers": "ready"}


@app.post("/ingest")
def ingest(req: IngestRequest) -> dict:
    try:
        return ingest_document(
            source=req.source,
            title=req.title,
            url=req.url,
            published_at=req.published_at,
            doc_type=req.doc_type,
            project=req.project,
            category=req.category,
            region=req.region,
            source_type=req.source_type,
            language=req.language,
            summary=req.summary,
            content=req.content,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/search")
def search_route(req: SearchRequest) -> dict:
    try:
        hits = search(query=req.query, top_k=req.top_k)
        return {"hits": hits}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/chat")
def chat_route(req: ChatRequest) -> dict:
    try:
        return chat(query=req.query, top_k=req.top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/market/coins")
def market_coins() -> dict:
    try:
        return {"coins": fetch_market_coins()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/market/briefs")
def market_briefs() -> dict:
    try:
        return fetch_market_briefs()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
