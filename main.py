import os
import io
import requests
import traceback
from typing import List
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from pypdf import PdfReader
from docx import Document

load_dotenv()

app = FastAPI(title="Enterprise RAG API - Management Ready")

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
LOVABLE_DELETE_URL = f"{LOVABLE_BASE_URL}/api/public/rag/delete"

class QueryRequest(BaseModel):
    question: str

@app.get("/")
def read_root():
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    secret_key = os.getenv("RAG_INGEST_SECRET")
    return {
        "status": "Enterprise RAG Service (Management Ready) is Live! 🚀",
        "api_key_status": "Present" if api_key else "Missing",
        "rag_secret_status": "Present" if secret_key else "Missing"
    }

def get_embedding(text: str, api_key: str):
    """توليد Embedding باستخدام نموذج gemini-embedding-001 بـ 1536 بعد"""
    from llama_index.embeddings.gemini import GeminiEmbedding
    
    embed_model = GeminiEmbedding(model_name="models/gemini-embedding-001", api_key=api_key)
    embedding = embed_model.get_text_embedding(text)
    
    if len(embedding) > 1536:
        embedding = embedding[:1536]
    elif len(embedding) < 1536:
        embedding = embedding + [0.0] * (1536 - len(embedding))
        
    return embedding

def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """استخراج النصوص بذكاء بناءً على نوع الملف (PDF, Word, TXT)"""
    file_ext = filename.split(".")[-1].lower()
    text = ""
    
    try:
        if file_ext == "pdf":
            reader = PdfReader(io.BytesIO(file_content))
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        elif file_ext in ["docx", "doc"]:
            doc = Document(io.BytesIO(file_content))
            for para in doc.paragraphs:
                if para.text:
                    text += para.text + "\n"
        else:
            text = file_content.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"Error parsing file {filename}: {e}")
        
    return text

@app.post("/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """نقطة دعم رفع ملفات متعددة (PDF, Word, TXT) ومعالجتها وفهرستها دفعة واحدة"""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    secret_key = os.getenv("RAG_INGEST_SECRET")
    
    if not api_key or not secret_key:
        raise HTTPException(status_code=500, detail="API Key or RAG Secret is missing")

    results = []
    headers = {
        "Content-Type": "application/json",
        "x-ingest-secret": secret_key
    }

    for file in files:
        try:
            content = await file.read()
            text = extract_text_from_file(content, file.filename)
            
            if not text.strip():
                results.append({"file_name": file.filename, "status": "skipped", "reason": "Empty or unreadable text"})
                continue

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

            payload = {
                "document": {
                    "file_name": file.filename,
                    "file_size": len(content),
                    "file_type": file.content_type or "application/octet-stream",
                    "page_count": max(1, len(text) // 2000)
                },
                "chunks": chunks_payload
            }

            response = requests.post(LOVABLE_INGEST_URL, json=payload, headers=headers, timeout=60)
            
            if response.status_code == 200:
                results.append({"file_name": file.filename, "status": "success", "chunks_count": len(chunks_payload)})
            else:
                results.append({"file_name": file.filename, "status": "failed", "error": response.text})

        except Exception as e:
            traceback.print_exc()
            results.append({"file_name": file.filename, "status": "error", "error": str(e)})

    return {"status": "batch_processed", "results": results}

@app.delete("/documents/{file_name}")
def delete_document(file_name: str):
    """نقطة حذف مستند معين ومتجهاته من النظام"""
    secret_key = os.getenv("RAG_INGEST_SECRET")
    if not secret_key:
        raise HTTPException(status_code=500, detail="RAG Secret is missing")

    try:
        headers = {
            "Content-Type": "application/json",
            "x-ingest-secret": secret_key
        }
        response = requests.delete(f"{LOVABLE_DELETE_URL}/{file_name}", headers=headers, timeout=15)
        
        if response.status_code == 200:
            return {"status": "success", "message": f"Document '{file_name}' deleted successfully."}
        else:
            return {"status": "info", "message": f"Delete request sent for '{file_name}'."}
    except Exception as e:
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
                    if isinstance(matches, dict):
                        matches = matches.get("matches", matches.get("results", []))
                        
                    context_chunks = []
                    for match in matches:
                        chunk_text = match.get("chunk_text") or match.get("content", "")
                        file_name = match.get("file_name") or match.get("metadata", {}).get("file_name", "Document")
                        similarity = match.get("similarity") or match.get("score", 0)
                        
                        if chunk_text:
                            context_chunks.append(f"[{file_name}]: {chunk_text}")
                            sources.append({"file_name": file_name, "score": similarity})
                    
                    context_str = "\n\n".join(context_chunks)
            except Exception as e:
                print(f"RAG Search warning: {e}")

        from llama_index.llms.gemini import Gemini
        
        gemini_llm = Gemini(model_name="models/gemini-3.8-flash", api_key=api_key)
        
        if context_str:
            prompt = (
                f"You are an enterprise AI assistant. Use the following retrieved document excerpts to answer the question accurately and cite the sources.\n\n"
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
