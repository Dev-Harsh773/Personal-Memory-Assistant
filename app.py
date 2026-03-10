"""
app.py — Unified Multimodal Search Server (Phase 2)

Serves the search UI and handles queries against both:
  - Image collection (CLIP embeddings)
  - Document collection (BGE-large embeddings)
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os
import uvicorn

# Import from Phase 1 (image search)
from main import get_text_embedding, setup_db

# Import from Phase 2 (document search)
from document_indexer import get_doc_query_embedding, setup_doc_db

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Initialize both ChromaDB collections
image_collection = setup_db()             # "image_memory" collection (CLIP 768-dim)
doc_collection = setup_doc_db()           # "document_memory" collection (BGE 1024-dim)


class SearchQuery(BaseModel):
    query: str


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main search UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/image")
async def get_image(path: str):
    """Serves an image file from a local path."""
    if os.path.exists(path) and os.path.isfile(path):
        return FileResponse(path)
    return HTMLResponse(status_code=404, content="Image not found")


@app.get("/file")
async def get_file(path: str):
    """Serves a document file for download/preview."""
    if os.path.exists(path) and os.path.isfile(path):
        return FileResponse(path, filename=os.path.basename(path))
    return HTMLResponse(status_code=404, content="File not found")


def _normalize_score(similarity, min_sim, max_sim):
    """Map a raw cosine similarity to a 0-100% scale given expected bounds."""
    normalized = (similarity - min_sim) / (max_sim - min_sim)
    return max(0.0, min(100.0, normalized * 100.0))


@app.post("/api/search")
async def search(search_query: SearchQuery):
    """
    Unified multimodal search:
    1. Embeds query with CLIP → searches image_memory
    2. Embeds query with BGE → searches document_memory
    3. Merges and ranks all results
    """
    query_text = search_query.query
    all_matches = []

    # --- IMAGE SEARCH (CLIP) ---
    image_embedding = get_text_embedding(query_text)
    if image_embedding:
        try:
            img_results = image_collection.query(
                query_embeddings=[image_embedding],
                n_results=10,
                include=["metadatas", "distances"]
            )
            if img_results and img_results.get("metadatas") and img_results.get("distances"):
                metadatas = img_results["metadatas"][0]
                distances = img_results["distances"][0]
                
                for i in range(len(metadatas)):
                    similarity = 1.0 - distances[i]
                    percentage = _normalize_score(similarity, 0.15, 0.35)
                    
                    if percentage > 0.0:
                        all_matches.append({
                            "type": "image",
                            "path": metadatas[i]["file_path"],
                            "percentage": round(percentage, 1),
                        })
        except Exception as e:
            print(f"Image search error: {e}")

    # --- DOCUMENT SEARCH (BGE) ---
    doc_embedding = get_doc_query_embedding(query_text)
    if doc_embedding:
        try:
            doc_results = doc_collection.query(
                query_embeddings=[doc_embedding],
                n_results=10,
                include=["metadatas", "distances"]
            )
            if doc_results and doc_results.get("metadatas") and doc_results.get("distances"):
                metadatas = doc_results["metadatas"][0]
                distances = doc_results["distances"][0]
                
                for i in range(len(metadatas)):
                    similarity = 1.0 - distances[i]
                    # BGE similarities range higher (~0.3 unrelated to ~0.85 strong match)
                    percentage = _normalize_score(similarity, 0.30, 0.85)
                    
                    if percentage > 0.0:
                        all_matches.append({
                            "type": "document",
                            "path": metadatas[i].get("file_path", ""),
                            "file_type": metadatas[i].get("file_type", "txt"),
                            "chunk_text": metadatas[i].get("chunk_text", ""),
                            "percentage": round(percentage, 1),
                        })
        except Exception as e:
            print(f"Document search error: {e}")

    # Sort all results by percentage (highest first)
    all_matches.sort(key=lambda x: x["percentage"], reverse=True)

    return {"results": all_matches}


if __name__ == "__main__":
    img_count = image_collection.count()
    doc_count = doc_collection.count()
    
    print("=" * 50)
    print("  Personal Memory Assistant — Unified Search")
    print("=" * 50)
    print(f"  Images indexed: {img_count}")
    print(f"  Document chunks indexed: {doc_count}")
    print(f"  Serving on http://localhost:8000")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
