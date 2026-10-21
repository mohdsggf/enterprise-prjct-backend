import os
import requests
import traceback
from fastapi import FastAPI, HTTPException
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

# بيانات الجسر الآمن من Lovable
LOVABLE_SEARCH_URL = "https://project--c5115517-92fe-4704-84c8-dbab9c792a46-dev.lovable.app/api/public/rag/search"
RAG_INGEST_SECRET = os.getenv("RAG_INGEST_SECRET")

class QueryRequest(BaseModel):
    question: str

@app.get("/")
def read_root():
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    key_status = "Present" if api_key else "Missing"
    secret_status = "Present" if RAG_INGEST_SECRET else "Missing"
    return {
        "status": "Enterprise RAG Service is Live! 🚀",
        "api_key_status": key_status,
        "rag_secret_status": secret_status
    }

def get_embedding(text: str, api_key: str):
    """توليد Embedding برقم أبعاد 1536 متوافق مع Lovable"""
    from llama_index.embeddings.gemini import GeminiEmbedding
    
    embed_model = GeminiEmbedding(model_name="models/text-embedding-004", api_key=api_key)
    embedding = embed_model.get_text_embedding(text)
    
    # تأكيد أو ضبط طول المتجه إلى 1536 إذا لزم الأمر
    if len(embedding) > 1536:
        embedding = embedding[:1536]
    elif len(embedding) < 1536:
        embedding = embedding + [0.0] * (1536 - len(embedding))
        
    return embedding

@app.post("/chat")
def chat(request: QueryRequest):
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    secret_key = os.getenv("RAG_INGEST_SECRET")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="API Key is missing in Render environment variables")

    try:
        context_str = ""
        sources = []
        
        # 1. محاولة إجراء البحث الدلالي في المستندات إذا كان المفتاح السري موجوداً
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
                
                search_response = requests.post(LOVABLE_SEARCH_URL, json=search_payload, headers=headers, timeout=10)
                
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

        # 2. إعداد المطالبة (Prompt) وإرسالها إلى Gemini
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
