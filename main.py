from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
import os

app = FastAPI()

# الرابط الخاص بقاعدة بيانات الإدارة الرئيسية (Master DB) الخاصة بمنصتك
MASTER_DB_URL = os.getenv("MASTER_DB_URL", "postgresql://postgres:كلمة_مرور_قاعدتك_الرئيسية@db.peugpsbflypaaeceroso.supabase.co:5432/postgres?sslmode=require")

class ClientRegistration(BaseModel):
    email: str
    client_db_url: str

class QueryRequest(BaseModel):
    email: str
    question: str

# 1. API تسجيل العميل وحفظ رابطه في Master DB
@app.post("/api/register-client")
def register_client(data: ClientRegistration):
    try:
        conn = psycopg2.connect(MASTER_DB_URL)
        cur = conn.cursor()
        # إدخال أو تحديث بيانات العميل
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
        raise HTTPException(status_code=500, detail=str(e))

# 2. API الاستعلام الذكي (يجلب الرابط تلقائياً بناءً على البريد)
@app.post("/api/query-database")
def query_database(data: QueryRequest):
    try:
        # أحياناً نقوم بالبحث عن رابط العميل من جدول الإدارة
        conn_master = psycopg2.connect(MASTER_DB_URL)
        cur_master = conn_master.cursor()
        cur_master.execute("SELECT client_db_url FROM clients WHERE email = %s", (data.email,))
        row = cur_master.fetchone()
        cur_master.close()
        conn_master.close()

        if not row:
            raise HTTPException(status_code=404, detail="العميل غير مسجل أو البريد الإلكتروني غير موجود في النظام.")
        
        client_db_url = row[0]

        # هنا يتم استخدام client_db_url المسترجع للاتصال بقاعدة بيانات العميل وتحليل البيانات عبر الذكاء الاصطناعي
        # (استدعاء دمج خريطة الجداول وتوليد الـ SQL ومعالجة السؤال هنا)
        
        return {
            "status": "success",
            "message": "تم العثور على رابط العميل بنجاح وجاهز لتنفيذ الاستعلام!",
            "retrieved_db_url": client_db_url,
            "question": data.question
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
