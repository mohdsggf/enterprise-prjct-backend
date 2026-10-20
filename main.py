import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from llama_index.core import Settings
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    gemini_llm = Gemini(model_name="gemini-1.5-flash", api_key=GOOGLE_API_KEY)
    gemini_embed = GeminiEmbedding(model_name="text-embedding-004", api_key=GOOGLE_API_KEY)
    
    Settings.llm = gemini_llm
    Settings.embed_model = gemini_embed

app = FastAPI(title="Enterprise RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str

@app.get("/")
def read_root():
    return {"status": "Enterprise RAG Service is Live! 🚀"}

@app.post("/chat")
def chat(request: QueryRequest):
    try:
        if not GOOGLE_API_KEY:
            raise HTTPException(status_code=500, detail="GOOGLE_API_KEY is missing on Render settings")
            
        response = Settings.llm.complete(request.question)
        return {
            "answer": str(response),
            "sources": []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
