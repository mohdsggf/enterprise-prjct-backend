import os
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

class QueryRequest(BaseModel):
    question: str

@app.get("/")
def read_root():
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    key_status = "Present" if api_key else "Missing"
    return {
        "status": "Enterprise RAG Service is Live! 🚀",
        "api_key_status": key_status
    }

@app.post("/chat")
def chat(request: QueryRequest):
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="API Key is missing in Render environment variables")

    try:
        from llama_index.llms.gemini import Gemini
        
        # استخدام نموذج gemini-2.0-flash المستقر والسريع
        gemini_llm = Gemini(model_name="models/gemini-2.0-flash", api_key=api_key)
        response = gemini_llm.complete(request.question)
        
        return {
            "answer": str(response),
            "sources": []
        }
    except Exception as e:
        error_details = f"Gemini Error: {str(e)}"
        print(f"CRITICAL ERROR: {error_details}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_details)
