import os
import requests
import traceback
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Enterprise RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# الرابط المعتمد للجسر الآمن من Lovable
LOVABLE_BASE_URL = "https://project--c5115517-92fe-4704-84c8-dbab9c792a46-dev.lovable.app"
LOVABLE_SEARCH_URL = f"{LOVABLE_BASE_URL}/api/public/rag/search"
LOVABLE_INGEST_URL = f"{LOVABLE_BASE_URL}/api/public/rag/ingest"

class QueryRequest(BaseModel):
    question: str

@app.get("/")
def read_root():
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    secret_key = os.getenv("RAG_INGEST_SECRET")
    return {
        "status": "Enterprise RAG Service is Live! 🚀",
        "api_key_status": "Present" if api_key else "Missing",
        "rag_secret_status": "Present" if secret_key else "Missing"
    }

def get_embedding(text: str, api_key: str):
    """توليد Embedding باستخدام النموذج الحديث gemini-embedding-001 بـ 1536 بعد"""
    from llama_index.embeddings.gemini import GeminiEmbedding
    
    embed_model = GeminiEmbedding(model_name="models/gemini-embedding-001", api_key=api_key)
    embedding = embed_model.get_text_embedding(text)
    
    if len(embedding) > 1536:
        embedding = embedding[:1536]
    elif len(embedding) < 1536:
        embedding = embedding + [0.0] * (1536 - len(embedding))
        
    return embedding

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """نقطة استلام المستندات، تقطيعها، واستخراج الـ Embeddings وإرسالها للـ Bridge"""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    secret_key = os.getenv("RAG_INGEST_SECRET")
    
    if not api_key or not secret_key:
        raise HTTPException(status_code=500, detail="API Key or RAG Secret is missing")

    try:
        content = await file.read()
        text = content.decode("utf-8", errors="ignore")
        
        if not text.strip():
            raise HTTPException(status_code=400, detail="File content is empty or unreadable text")

        # تقطيع النص إلى فقرات
        chunks_text = [text[i:i+1000] for i in range(0, len(text), 800)]
        
        chunks_payload = []
        for index, chunk_str in enumerate(chunks_text):
            emb = get_embedding(chunk_str, api_key)
            chunks_payload.append({
                "chunk_index": index,
                "chunk_text": chunk_str,
                "page_number": 1,
                "metadata": {},
                "embedding": emb
            })

        headers = {
            "Content-Type": "application/json",
            "x-ingest-secret": secret_key
        }

        payload = {
            "document": {
                "file_name": file.filename,
                "file_size": len(content),
                "file_type": file.content_type or "text/plain",
                "page_count": 1
            },
            "chunks": chunks_payload
        }

        response = requests.post(LOVABLE_INGEST_URL, json=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {response.text}")

        return {"status": "success", "file_name": file.filename, "chunks_count": len(chunks_payload)}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
def chat(request: QueryRequest):
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    secret_key = os.getenv("RAG_INGEST_SECRET")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="API Key is missing")

    try:
        context_str = ""
        sources = []
        
        if secret_key:
            try:
                query_embedding = get_embedding(request.question, api_key)
                
                headers = {
                    "Content-Type": "application/json",
                    "x-ingest-secret": secret_key
                }
                
                search_payload = {
                    "embedding": query_embedding,
                    "match_count": 5
                }
                
                search_response = requests.post(LOVABLE_SEARCH_URL, json=search_payload, headers=headers, timeout=15)
                
                if search_response.status_code == 200:
                    matches = search_response.json()
                    context_chunks = []
                    for match in matches:
                        chunk_text = match.get("chunk_text", "")
                        file_name = match.get("file_name", "Document")
                        context_chunks.append(f"[{file_name}]: {chunk_text}")
                        sources.append({"file_name": file_name, "score": match.get("similarity", 0)})
                    
                    context_str = "\n\n".join(context_chunks)
            except Exception as e:
                print(f"RAG Search warning: {e}")

        from llama_index.llms.gemini import Gemini
        
        gemini_llm = Gemini(model_name="models/gemini-3.8-flash", api_key=api_key)
        
        if context_str:
            prompt = (
                f"You are an enterprise AI assistant. Use the following retrieved document excerpts to answer the question accurately.\n\n"
                f"Context:\n{context_str}\n\n"
                f"Question: {request.question}\n\n"
                f"Answer:"
            )
        else:
            prompt = request.question

        response = gemini_llm.complete(prompt)
        
        return {
            "answer": str(response),
            "sources": sources
        }
        
    except Exception as e:
        error_details = f"Gemini/RAG Error: {str(e)}"
        print(f"CRITICAL ERROR: {error_details}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_details)
