@app.post("/api/register-client")
def register_client(data: ClientRegistration):
    if not MASTER_DB_URL:
        raise HTTPException(status_code=500, detail="MASTER_DB_URL environment variable is not configured.")
    try:
        print(f"Attempting to connect with MASTER_DB_URL...") # للتحقق في السجلات
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
        print(f"CRITICAL ERROR in register_client: {str(e)}") # طباعة الخطأ بوضوح في رندر
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
