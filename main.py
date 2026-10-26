import os
import sqlite3
import json
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai

app = FastAPI(title="Enterprise AI Engine & Text-to-SQL")

# إعدادات CORS للسماح لـ Lovable بالاتصال بالـ Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# تهيئة Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

DB_FILE = "demo_company.db"

# 1. إنشاء قاعدة بيانات تجريبية محلياً عند تشغيل السيرفر
def init_demo_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # إنشاء جدول المبيعات
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
    
    # التأكد من عدم تكرار إضافة البيانات التجريبية
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

# تشغيل تهيئة قاعدة البيانات عند إقلاع السيرفر
init_demo_db()

class QueryRequest(BaseModel):
    question: str

@app.post("/api/query-database")
def query_database(req: QueryRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API Key is missing.")
    
    try:
        # Schema الخاصة بقاعدة البيانات
        db_schema = """
        Table: sales
        Columns:
        - id: INTEGER (Primary Key)
        - branch: TEXT (اسم الفرع، مثل 'فرع الروضة', 'فرع العليا', 'فرع الشاطئ', 'فرع الفيصلية')
        - city: TEXT (المدينة، مثل 'جدة', 'الرياض', 'الدمام')
        - product_name: TEXT (اسم المنتج)
        - category: TEXT (الفئة، مثل 'وجبات', 'مقبلات', 'مشروبات', 'حلويات')
        - quantity: INTEGER (الكمية المباعة)
        - unit_price: REAL (سعر الوحدة بالريال)
        - total_amount: REAL (المبلغ الإجمالي بالريال = quantity * unit_price)
        - sale_date: DATE (تاريخ البيع بتنسيق YYYY-MM-DD)
        """

        prompt = f"""
        You are an expert SQLite SQL developer. 
        Database Schema:
        {db_schema}

        User Question: "{req.question}"

        Tasks:
        1. Generate a valid SQLite SQL query to answer the user question.
        2. Return ONLY the raw SQL query without any explanation, markdown, code blocks (```sql), or extra text.
        """

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        sql_query = response.text.strip().replace("```sql", "").replace("```", "").strip()

        # تنفيذ استعلام SQL على قاعدة البيانات
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        conn.close()

        # صياغة الملخص والبطاقات عبر Gemini بناءً على النتائج
        summary_prompt = f"""
        السؤال: "{req.question}"
        استعلام SQL المنفذ: "{sql_query}"
        نتائج قاعدة البيانات:
        الأعمدة: {columns}
        الصفوف: {rows}

        المطلوب: قم بصياغة إجابة ملخصة واحترافية باللغة العربية تشرح نتائج البيانات بدقة وبساطة.
        """
        summary_res = model.generate_content(summary_prompt)

        # تحضير الهيكل المسترجع لـ Lovable
        formatted_table = {
            "columns": columns,
            "rows": [dict(zip(columns, row)) for row in rows]
        }

        # إنشاء بطاقات أرقام تلقائية في حال وجود مجاميع أو أعداد
        metrics = []
        if len(rows) == 1 and len(columns) == 1:
            metrics.append({"label": columns[0], "value": str(rows[0][0])})

        return {
            "summary": summary_res.text.strip(),
            "sql_query": sql_query,
            "table": formatted_table,
            "metrics": metrics
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Query Error: {str(e)}")
