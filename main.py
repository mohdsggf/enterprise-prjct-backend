import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# منع LlamaIndex من البحث عن مفاتيح OpenAI افتراضياً
os.environ["OPENAI_API_KEY"] = "dummy-key-to-bypass-llamaindex-default"

from llama_index.core import Settings
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding

load_dotenv()

app = FastAPI(title="Enterprise RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    try:
        # تعيين نموذج اللسان ونموذج التضمين من جوجل بشكل صارم
        Settings.llm = Gemini(model_name="models/gemini-1.5-flash-latest", api_key=GOOGLE_API_KEY)
        Settings.embed_model = GeminiEmbedding(model_name="models/text-embedding-004", api_key=GOOGLE_API_KEY)
    except Exception as e:
        print(f"Error initializing Gemini: {e}")

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
