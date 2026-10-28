import os
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 1. تعريف التطبيق أولاً قبل أي مسارات أو decorators
app = FastAPI(title="Enterprise Sovereign AI Engine")

# 2. تفعيل الـ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. جلب رابط قاعدة بيانات الإدارة
MASTER_DB_URL = os.getenv("MASTER_DB_URL")

class ClientRegistration(BaseModel):
    email: str
    client_db_url: str

class QueryRequest(BaseModel):
    email: str
    question: str

@app.get("/")
def read_root():
    return {"status": "online", "message": "SaaS AI Engine Backend Running"}

# 4. مسار تسجيل العميل
@app.post("/api/register-client")
def register_client(data: ClientRegistration):
    if not MASTER_DB_URL:
        raise HTTPException(status_code=500, detail="MASTER_DB_URL environment variable is not configured.")
    try:
        print(f"Attempting to connect with MASTER_DB_URL...")
        conn = psycopg2.connect(MASTER_DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                client_db_url TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cur.execute(
            """
            INSERT INTO clients (email, client_db_url) 
            VALUES (%s, %s)
            ON CONFLICT (email) 
            DO UPDATE SET client_db_url = EXCLUDED.client_db_url;
            """,
            (data.email, data.client_db_url)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "success", "message": "تم تسجيل العميل وحفظ رابط قاعدة البيانات بنجاح!"}
    except Exception as e:
        print(f"CRITICAL ERROR in register_client: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# 5. مسار الاستعلام الذكي
@app.post("/api/query-database")
def query_database(data: QueryRequest):
    if not MASTER_DB_URL:
        raise HTTPException(status_code=500, detail="MASTER_DB_URL environment variable is not configured.")
    try:
        conn_master = psycopg2.connect(MASTER_DB_URL)
        cur_master = conn_master.cursor()
        cur_master.execute("SELECT client_db_url FROM clients WHERE email = %s", (data.email,))
        row = cur_master.fetchone()
        cur_master.close()
        conn_master.close()

        if not row:
            raise HTTPException(status_code=404, detail="العميل غير مسجل، يرجى حفظ بيانات الربط في صفحة الإعدادات أولاً.")
        
        client_db_url = row[0]

        return {
            "status": "success",
            "message": "تم استرجاع قاعدة بيانات العميل بنجاح وتجهيز الاستعلام!",
            "client_email": data.email,
            "question": data.question
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
