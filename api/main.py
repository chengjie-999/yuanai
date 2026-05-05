from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1 import init_router
from api.v1.chat.router import router as chat_router
from api.v1.tools.router import router as tools_router
from api.v1.browser.router import router as browser_router
from api.v1.monitor.router import router as monitor_router

app = FastAPI(title="Spider API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:5173",
        "https://你的正式前端域名.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

spider_router = init_router()
app.include_router(spider_router, prefix="/api/v1/spider", tags=["spider"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(tools_router, prefix="/api/v1", tags=["tools"])
app.include_router(browser_router, prefix="/api/v1", tags=["browser"])
app.include_router(monitor_router, prefix="/api/v1", tags=["monitor"])


@app.get("/")
def root():
    return {"message": "Spider API is running6"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
