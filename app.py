from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import chromadb
from typing import List, Optional, Dict
from loguru import logger
from prometheus_client import Counter, Histogram, start_http_server
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI(title="JurisAI Semantic Search API")

# Logging
logger.add("logs/api.log", rotation="1 week", retention="1 month", level="INFO")

# Prometheus metrics
REQUEST_COUNT = Counter("request_count", "Total API requests", ["endpoint"])
REQUEST_LATENCY = Histogram("request_latency_seconds", "Request latency", ["endpoint"])

start_http_server(9000)  # Expose Prometheus metrics on :9000

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def prometheus_middleware(request, call_next):
    import time
    endpoint = request.url.path
    REQUEST_COUNT.labels(endpoint=endpoint).inc()
    start = time.time()
    response = await call_next(request)
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(time.time() - start)
    return response

# Embedding & Vector DB (modular, ready for DI/future swap)
class EmbeddingEngine:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
    def encode(self, texts):
        return self.model.encode(texts)

class VectorStore:
    def __init__(self, collection_name="legal_docs"):
        self.client = chromadb.Client()
        if collection_name in [c.name for c in self.client.list_collections()]:
            self.collection = self.client.get_collection(collection_name)
        else:
            self.collection = self.client.create_collection(collection_name)
    def add(self, embedding, content, metadata, doc_id):
        self.collection.add(
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata],
            ids=[doc_id]
        )
    def search(self, embedding, n_results):
        return self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results
        )
    def count(self):
        return self.collection.count()

embedder = EmbeddingEngine()
vector_store = VectorStore()

class SearchQuery(BaseModel):
    query: str
    max_results: int = 10
    filters: Optional[Dict] = None

class Document(BaseModel):
    id: str
    content: str
    metadata: dict
    score: float

@app.get("/")
def read_root():
    return {"message": "JurisAI API v2.0", "status": "operational"}

@app.post("/search", response_model=List[Document])
async def semantic_search(query: SearchQuery):
    try:
        query_embedding = embedder.encode([query.query])[0]
        results = vector_store.search(query_embedding, query.max_results)
        documents = []
        for i, doc_id in enumerate(results['ids'][0]):
            documents.append(Document(
                id=doc_id,
                content=results['documents'][0][i],
                metadata=results['metadatas'][0][i],
                score=results['distances'][0][i]
            ))
        return documents
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/index")
async def index_document(content: str, metadata: str = Query("{}")):
    print('>>> [DEBUG] Entrée dans /index avec content:', content)
    try:
        # Parse metadata string en dict si besoin
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        embedding = embedder.encode([content])[0].tolist()
        doc_id = f"doc_{vector_store.count() + 1}"
        vector_store.add(embedding, content, metadata, doc_id)
        return {"status": "indexed", "id": doc_id}
    except Exception as e:
        import traceback
        print('Exception in /index:', traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    return {
        "total_documents": vector_store.count(),
        "model": "all-MiniLM-L6-v2",
        "status": "healthy"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "ml_models": "loaded",
        "db": "connected"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 