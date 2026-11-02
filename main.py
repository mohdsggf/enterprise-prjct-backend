import os
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
from typing import Optional
from sqlalchemy import create_engine, inspect, text

app = FastAPI(title="Enterprise Multi-Database Sovereign AI Engine")

# تفعيل الـ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# جلب متغيرات البيئة
MASTER_DB_URL = os.getenv("MASTER_DB_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class ClientRegistration(BaseModel):
    email: str
    client_db_url: str

class QueryRequest(BaseModel):
    email: str
    question: str

# دالة مساعدة لتنظيف وتنسيق رابط قاعدة البيانات ليعمل مع SQLAlchemy
def format_db_url(url: str) -> str:
    cleaned_url = url.strip()
    if cleaned_url.startswith("postgres://"):
        return cleaned_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif cleaned_url.startswith("postgresql://") and not cleaned_url.startswith("postgresql+psycopg2://"):
        return cleaned_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return cleaned_url

def verify_token(authorization: Optional[str] = Header(None)):
    return authorization

@app.get("/")
def read_root():
    return {"status": "online", "message": "Multi-DB SaaS AI Engine Backend Running"}

# 1. مسار تسجيل العميل وحفظ رابط قاعدته
@app.post("/api/register-client")
def register_client(data: ClientRegistration, token: str = Depends(verify_token)):
    if not MASTER_DB_URL:
        raise HTTPException(status_code=500, detail="MASTER_DB_URL environment variable is not configured.")
    try:
        formatted_master_url = format_db_url(MASTER_DB_URL)
        master_engine = create_engine(formatted_master_url)
        
        formatted_client_url = format_db_url(data.client_db_url)
        
        # التأكد أولاً من صحة رابط العميل عبر محاولة الاتصال به قبل الحفظ
        test_client_engine = create_engine(formatted_client_url)
        with test_client_engine.connect() as test_conn:
            pass

        with master_engine.connect() as conn:
            # إنشاء جدول clients في قاعدة الإدارة إذا لم يكن موجوداً
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS clients (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    client_db_url TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            conn.execute(
                text("""
                    INSERT INTO clients (email, client_db_url) 
                    VALUES (:email, :db_url)
                    ON CONFLICT (email) 
                    DO UPDATE SET client_db_url = EXCLUDED.client_db_url;
                """),
                {"email": data.email.lower().strip(), "db_url": formatted_client_url}
            )
            conn.commit()
        return {"status": "success", "message": "تم تسجيل العميل وحفظ رابط قاعدة البيانات بنجاح!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

# 2. مسار الاستعلام الذكي المتعدد (Text-to-SQL)
@app.post("/api/query-database")
def query_database(data: QueryRequest, token: str = Depends(verify_token)):
    if not MASTER_DB_URL or not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Configuration error.")
    
    try:
        # أ. جلب رابط قاعدة بيانات العميل من الـ Master DB
        formatted_master_url = format_db_url(MASTER_DB_URL)
        master_engine = create_engine(formatted_master_url)
        
        with master_engine.connect() as conn:
            result = conn.execute(
                text("SELECT client_db_url FROM clients WHERE email = :email"),
                {"email": data.email.lower().strip()}
            )
            row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="العميل غير مسجل، يرجى إكمال إعدادات الربط أولاً.")
        
        client_db_url = format_db_url(row[0])

        # ب. الاتصال بقاعدة بيانات العميل وسحب هيكل الجداول
        client_engine = create_engine(client_db_url)
        inspector = inspect(client_engine)
        
        schema_description = {}
        for table_name in inspector.get_table_names():
            schema_description[table_name] = []
            for col in inspector.get_columns(table_name):
                schema_description[table_name].append(f"{col['name']} ({col['type']})")

        schema_text = "\n".join([f"Table '{t}': " + ", ".join(cols) for t, cols in schema_description.items()])

        # ج. توليد استعلام SQL آمن باستخدام gemini-3.8-flash
        model = genai.GenerativeModel('gemini-3.8-flash')
        prompt = f"""
        You are an expert database and SQL assistant. Given the following database schema:
        {schema_text}

        Write a safe, read-only SQL SELECT query to answer this user question: "{data.question}"
        Return ONLY the raw SQL query inside a markdown code block or plain text, nothing else. No explanation.
        """
        
        response = model.generate_content(prompt)
        sql_query = response.text.strip().replace("```sql", "").replace("```", "").strip()

        if not sql_query.lower().startswith("select"):
            raise HTTPException(status_code=400, detail="Generated query is not a valid read-only SELECT statement.")

        # د. تنفيذ الاستعلام على قاعدة بيانات العميل
        with client_engine.connect() as client_conn:
            result_proxy = client_conn.execute(text(sql_query))
            column_names = list(result_proxy.keys())
            query_results = [list(row) for row in result_proxy.fetchall()]

        # هـ. صياغة الإجابة النهائية باللغة العربية
        format_prompt = f"""
        User Question: {data.question}
        SQL Query Used: {sql_query}
        Query Results (Rows): {query_results[:50]} (Columns: {column_names})

        Provide a clear, professional, and natural language response in Arabic answering the user's question based on these results.
        """
        format_response = model.generate_content(format_prompt)
        final_answer = format_response.text

        return {
            "status": "success",
            "sql_query": sql_query,
            "columns": column_names,
            "rows": query_results,
            "answer": final_answer
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution error: {str(e)}")
