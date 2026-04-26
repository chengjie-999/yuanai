from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1 import init_router

# 终端1：启动 API 服务
# uvicorn api.main:app --reload --port 8000
app = FastAPI(title="Spider API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    # 只允许你自己的前端地址
    allow_origins=[
        "http://localhost:8080",
        "https://你的正式前端域名.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

spider_router = init_router()
app.include_router(spider_router, prefix="/api/v1/spider", tags=["spider"])


@app.get("/")
def root():
    return {"message": "Spider API is running6"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
