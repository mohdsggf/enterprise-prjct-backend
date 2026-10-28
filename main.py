import os
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Enterprise Sovereign AI Engine")

# تفعيل CORS للتسمح لواجهة Lovable بالاتصال بالباك إند بدون حظر من المتصفح
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# جلب رابط Master DB من متغيرات البيئة في Render
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

# 1. API تسجيل العميل وحفظ رابطه في Master DB
@app.post("/api/register-client")
def register_client(data: ClientRegistration):
    if not MASTER_DB_URL:
        raise HTTPException(status_code=500, detail="MASTER_DB_URL environment variable is not configured.")
    try:
        conn = psycopg2.connect(MASTER_DB_URL)
        cur = conn.cursor()
        
        # إنشاء الجدول في حال لم يكن موجوداً
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                client_db_url TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # حفظ أو تحديث رابط العميل
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
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

# 2. API الاستعلام الذكي (يجلب الرابط تلقائياً بناءً على البريد)
@app.post("/api/query-database")
def query_database(data: QueryRequest):
    if not MASTER_DB_URL:
        raise HTTPException(status_code=500, detail="MASTER_DB_URL environment variable is not configured.")
    try:
        # البحث عن رابط العميل في Master DB
        conn_master = psycopg2.connect(MASTER_DB_URL)
        cur_master = conn_master.cursor()
        cur_master.execute("SELECT client_db_url FROM clients WHERE email = %s", (data.email,))
        row = cur_master.fetchone()
        cur_master.close()
        conn_master.close()

        if not row:
            raise HTTPException(status_code=404, detail="العميل غير مسجل، يرجى حفظ بيانات الربط في صفحة الإعدادات أولاً.")
        
        client_db_url = row[0]

        # هنا يتصل السيرفر بقاعدة بيانات العميل لتنفيذ الاستعلام
        return {
            "status": "success",
            "message": "تم استرجاع قاعدة بيانات العميل بنجاح وتجهيز الاستعلام!",
            "client_email": data.email,
            "question": data.question
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
