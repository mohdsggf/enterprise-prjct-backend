import os
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai

app = FastAPI(title="Enterprise Sovereign AI Engine")

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

@app.get("/")
def read_root():
    return {"status": "online", "message": "SaaS AI Engine Backend Running"}

# 1. مسار تسجيل العميل
@app.post("/api/register-client")
def register_client(data: ClientRegistration):
    if not MASTER_DB_URL:
        raise HTTPException(status_code=500, detail="MASTER_DB_URL environment variable is not configured.")
    try:
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
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# 2. مسار الاستعلام الذكي (Text-to-SQL RAG Engine)
@app.post("/api/query-database")
def query_database(data: QueryRequest):
    if not MASTER_DB_URL:
        raise HTTPException(status_code=500, detail="MASTER_DB_URL environment variable is not configured.")
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY environment variable is not configured.")
    
    try:
        # أ. جلب رابط قاعدة بيانات العميل من الـ Master DB بناءً على البريد
        conn_master = psycopg2.connect(MASTER_DB_URL)
        cur_master = conn_master.cursor()
        cur_master.execute("SELECT client_db_url FROM clients WHERE email = %s", (data.email,))
        row = cur_master.fetchone()
        cur_master.close()
        conn_master.close()

        if not row:
            raise HTTPException(status_code=404, detail="العميل غير مسجل، يرجى حفظ بيانات الربط في صفحة الإعدادات أولاً.")
        
        client_db_url = row[0]

        # ب. الاتصال بقاعدة بيانات العميل وسحب هيكل الجداول (Schema)
        client_conn = psycopg2.connect(client_db_url)
        client_cur = client_conn.cursor()
        
        client_cur.execute("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public';
        """)
        schema_rows = client_cur.fetchall()
        
        schema_description = {}
        for table, col, dtype in schema_rows:
            if table not in schema_description:
                schema_description[table] = []
            schema_description[table].append(f"{col} ({dtype})")

        schema_text = "\n".join([f"Table '{t}': " + ", ".join(cols) for t, cols in schema_description.items()])

        # ج. استخدام النموذج المحدث gemini-2.0-flash لتوليد استعلام SQL آمن
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = f"""
        You are an expert SQL assistant. Given the following database schema of the client:
        {schema_text}

        Write a safe, read-only SQL SELECT query to answer this user question: "{data.question}"
        Return ONLY the raw SQL query inside a markdown code block or plain text, nothing else. No explanation.
        """
        
        response = model.generate_content(prompt)
        sql_query = response.text.strip().replace("```sql", "").replace("```", "").strip()

        # التحقق من أن الاستعلام آمن وقراءة فقط (SELECT)
        if not sql_query.lower().startswith("select"):
            raise HTTPException(status_code=400, detail="Generated query is not a valid read-only SELECT statement.")

        # د. تنفيذ الاستعلام على قاعدة بيانات العميل
        client_cur.execute(sql_query)
        query_results = client_cur.fetchall()
        column_names = [desc[0] for desc in client_cur.description] if client_cur.description else []
        
        client_cur.close()
        client_conn.close()

        # هـ. صياغة الإجابة النهائية باللغة العربية بواسطة النموذج
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
