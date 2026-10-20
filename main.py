import os
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

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# استيراد نموذج Gemini واستخدامه مباشرة بدون تمرير عبر إعدادات Settings العامة لـ LlamaIndex
from llama_index.llms.gemini import Gemini

gemini_llm = None
if GOOGLE_API_KEY:
    try:
        gemini_llm = Gemini(model_name="gemini-1.5-flash", api_key=GOOGLE_API_KEY)
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
        if not GOOGLE_API_KEY or not gemini_llm:
            raise HTTPException(status_code=500, detail="GOOGLE_API_KEY is missing or Gemini failed to initialize")
            
        # استخدام نموذج Gemini مباشرة لتجنب أي استدعاء وهمي لـ OpenAI
        response = gemini_llm.complete(request.question)
        return {
            "answer": str(response),
            "sources": []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
