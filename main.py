import os
import sqlite3
import json
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="Enterprise Sovereign AI & Text-to-SQL Engine")

# إعدادات CORS للسماح لـ Lovable بالاتصال بالـ Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# تهيئة Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

DEFAULT_DB_FILE = "demo_company.db"

def init_demo_db():
    """إنشاء قاعدة بيانات تجريبية محلية للاختبار"""
    conn = sqlite3.connect(DEFAULT_DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            branch VARCHAR(50),
            city VARCHAR(50),
            product_name VARCHAR(100),
            category VARCHAR(50),
            quantity INTEGER,
            unit_price REAL,
            total_amount REAL,
            sale_date DATE
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM sales")
    if cursor.fetchone()[0] == 0:
        sample_sales = [
            ('فرع الروضة', 'جدة', 'وجبة برجر دبل', 'وجبات', 150, 35.0, 5250.0, '2026-10-01'),
            ('فرع الروضة', 'جدة', 'بطاطس سوبر', 'مقبلات', 200, 15.0, 3000.0, '2026-10-01'),
            ('فرع العليا', 'الرياض', 'وجبة برجر دبل', 'وجبات', 300, 35.0, 10500.0, '2026-10-02'),
            ('فرع العليا', 'الرياض', 'عصير برتقال طازج', 'مشروبات', 120, 12.0, 1440.0, '2026-10-02'),
            ('فرع الشاطئ', 'جدة', 'وجبة دجاج كريسبي', 'وجبات', 180, 30.0, 5400.0, '2026-10-03'),
            ('فرع الشاطئ', 'جدة', 'حلى تشيز كيك', 'حلويات', 90, 22.0, 1980.0, '2026-10-03'),
            ('فرع الفيصلية', 'الدمام', 'وجبة برجر دبل', 'وجبات', 110, 35.0, 3850.0, '2026-10-04'),
            ('فرع الفيصلية', 'الدمام', 'بطاطس سوبر', 'مقبلات', 140, 15.0, 2100.0, '2026-10-04'),
            ('فرع الروضة', 'جدة', 'عصير برتقال طازج', 'مشروبات', 210, 12.0, 2520.0, '2026-10-05'),
            ('فرع العليا', 'الرياض', 'حلى تشيز كيك', 'حلويات', 150, 22.0, 3300.0, '2026-10-05')
        ]
        cursor.executemany('''
            INSERT INTO sales (branch, city, product_name, category, quantity, unit_price, total_amount, sale_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_sales)
        conn.commit()
    conn.close()

init_demo_db()

class QueryRequest(BaseModel):
    question: str
    db_url: str = None  # رابط الاتصال الاختياري لقاعدة بيانات العميل (مثل PostgreSQL)

def generate_sql_with_gemini(prompt_text: str):
    """استدعاء Gemini لتوليد الـ SQL فقط (طلب واحد لتقليل استهلاك الكوتا)"""
    model = genai.GenerativeModel("gemini-3.8-flash")
    res = model.generate_content(prompt_text)
    if res and res.text:
        return res.text
    raise Exception("Model returned empty response.")

def execute_query(db_url: str, sql_query: str):
    """تنفيذ استعلام SQL بناءً على نوع قاعدة البيانات (SQLite أو PostgreSQL)"""
    if db_url and db_url.startswith("postgres"):
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        if rows:
            columns = list(rows[0].keys())
            formatted_rows = [list(row.values()) for row in rows]
        else:
            columns = []
            formatted_rows = []
        conn.close()
        return columns, formatted_rows
    else:
        conn = sqlite3.connect(DEFAULT_DB_FILE)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        conn.close()
        return columns, rows

@app.post("/api/query-database")
def query_database(req: QueryRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API Key is missing.")
    
    try:
        db_schema = """
        Table: sales
        Columns:
        - id: INTEGER (Primary Key)
        - branch: TEXT (اسم الفرع، مثل 'فرع الروضة', 'فرع العليا')
        - city: TEXT (المدينة، مثل 'جدة', 'الرياض')
        - product_name: TEXT (اسم المنتج)
        - category: TEXT (الفئة)
        - quantity: INTEGER (الكمية المباعة)
        - unit_price: REAL (سعر الوحدة)
        - total_amount: REAL (المبلغ الإجمالي)
        - sale_date: DATE (تاريخ البيع YYYY-MM-DD)
        """

        prompt = f"""
        You are an expert SQL developer. 
        Database Schema:
        {db_schema}

        User Question: "{req.question}"

        Tasks:
        1. Generate a valid SQL query to answer the user question.
        2. Return ONLY the raw SQL query without any explanation, markdown, code blocks (```sql), or extra text.
        """

        # طلب واحد فقط لـ Gemini لتوليد الـ SQL
        raw_sql_response = generate_sql_with_gemini(prompt)
        sql_query = raw_sql_response.strip().replace("```sql", "").replace("```", "").strip()

        # تنفيذ الاستعلام
        columns, rows = execute_query(req.db_url, sql_query)

        # صياغة الملخص محلياً بدون استهلاك إضافي للـ API
        summary_text = f"إليك النتائج المستخرجة بناءً على سؤالك (تم العثور على {len(rows)} نتيجة):"

        formatted_table = {
            "columns": columns,
            "rows": [dict(zip(columns, row)) for row in rows]
        }

        metrics = []
        if len(rows) == 1 and len(columns) == 1:
            metrics.append({"label": columns[0], "value": str(rows[0][0])})

        return {
            "summary": summary_text,
            "sql_query": sql_query,
            "table": formatted_table,
            "metrics": metrics
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Query Error: {str(e)}")
