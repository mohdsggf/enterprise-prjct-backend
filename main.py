import os
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Cortex AI Engine API",
    description="Multi-tenant Enterprise RAG & Text-to-SQL Backend",
    version="1.0.0"
)

# 1. إعدادات CORS للسماح بالاتصال من واجهة Lovable
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # يمكنك تحديد رابط Lovable الخاص بك لاحقاً للأمان
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. الهيكل القياسي لبيانات الطلب القادم من الشات
class QueryRequest(BaseModel):
    prompt: str

# 3. متحكم هوية المستأجر (Multi-tenant Security Dependency)
async def get_tenant_id(x_tenant_id: Optional[str] = Header(None)) -> str:
    """
    يقرأ X-Tenant-ID من رأس الطلب ويرفض المعاملة أمنياً إذا كانت الهوية مفقودة.
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Tenant-ID header. Data isolation is enforced."
        )
    return x_tenant_id

# 4. مسار فحص حالة السيرفر على Render
@app.get("/")
async def health_check():
    return {
        "status": "online",
        "system": "Cortex Neural Core",
        "version": "1.0.0"
    }

# 5. مسار استعلام الـ RAG و Text-to-SQL المعزول برقم المستأجر
@app.post("/api/v1/query")
async def process_query(
    request: QueryRequest,
    tenant_id: str = Depends(get_tenant_id)
):
    """
    يستقبل السؤال، ويفصل الاستعلام بناءً على tenant_id لضمان عدم تداخل البيانات.
    """
    # هنا يتم ربط الاتصال بقاعدة بيانات العميل وتمرير السياق لـ Gemini
    # تم إدراج نموذج استجابة تجريبي للتأكد من نجاح عملية الربط والعزل
    
    return {
        "status": "success",
        "tenant_id": tenant_id,
        "query_received": request.prompt,
        "answer": f"تمت معالجة استعلامك بنجاح لصالح المؤسسة ({tenant_id}).",
        "data": []
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
