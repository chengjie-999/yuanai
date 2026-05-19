import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from api.v1 import init_router
from api.v1.chat.router import router as chat_router
from api.v1.tools.router import router as tools_router
from api.v1.auth.router import router as auth_router
from api.v1.stats.router import router as stats_router
from api.v1.admin.router import router as admin_router
from api.v1.data.router import router as data_router
from api.v1.middleware import auth_middleware
from utils.data_path import root_path

app = FastAPI(title="小元AI API", version="1.0.0")

_CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else [
    "http://localhost:8080",
    "http://localhost:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

qimg_dir = os.path.join(root_path(), 'data', 'qimg')
os.makedirs(qimg_dir, exist_ok=True)
chat_img_dir = os.path.join(root_path(), 'data', 'chat_images')
os.makedirs(chat_img_dir, exist_ok=True)

spider_router = init_router()
app.include_router(spider_router, prefix="/api/v1/spider", tags=["spider"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(tools_router, prefix="/api/v1", tags=["tools"])
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(stats_router, prefix="/api/v1", tags=["stats"])
app.include_router(admin_router, prefix="/api/v1", tags=["admin"])
app.include_router(data_router, prefix="/api/v1", tags=["data"])

app.middleware("http")(auth_middleware)


@app.get("/")
def root():
    return {"message": "小元AI API 运行中"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
