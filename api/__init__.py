"""
API 模块 - FastAPI 服务（独立运行）
用于提供浏览器操作的 HTTP API

启动方式：
    python -m api
或
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""
from contextlib import asynccontextmanager
from typing import Dict
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from spiderlx.auto.web.selenium.main import MyWebBrowser, BrowserInitializer

# 全局浏览器缓存
browser_sessions: Dict[str, MyWebBrowser] = {}


# ========== 请求/响应模型 ==========
class BrowserCreateResponse(BaseModel):
    session_id: str
    status: str = "created"


class BrowserCloseResponse(BaseModel):
    status: str = "closed"


class BrowserInfoResponse(BaseModel):
    session_id: str
    current_url: str = ""
    title: str = ""


# ========== 生命周期 ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    print("🚀 API 服务启动")
    yield
    print("🔌 关闭所有浏览器...")
    for session in list(browser_sessions.values()):
        try:
            session.close_browser()
        except:
            pass
    browser_sessions.clear()


# ========== 创建应用 ==========
def create_app() -> FastAPI:
    app = FastAPI(
        title="my_spider Browser API",
        description="浏览器操作 API",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS 配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/browser/create", response_model=BrowserCreateResponse)
    def create_browser():
        try:
            driver = BrowserInitializer().create_driver()
            session_id = driver.session_id
            browser = MyWebBrowser(driver)
            browser_sessions[session_id] = browser
            print(f"✅ 浏览器创建: {session_id}")
            return BrowserCreateResponse(session_id=session_id)
        except Exception as e:
            print(f"❌ 浏览器创建失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/browser/close", response_model=BrowserCloseResponse)
    def close_browser(session_id: str = None):
        if session_id and session_id in browser_sessions:
            browser_sessions[session_id].close_browser()
            del browser_sessions[session_id]
        if not session_id:
            for sid in list(browser_sessions.keys()):
                browser_sessions[sid].close_browser()
            browser_sessions.clear()
        return BrowserCloseResponse()

    @app.get("/browser/info", response_model=BrowserInfoResponse)
    def get_browser_info(session_id: str = None):
        if not session_id and browser_sessions:
            session_id = list(browser_sessions.keys())[0]
        if session_id not in browser_sessions:
            raise HTTPException(status_code=404, detail="没有活跃的浏览器")
        browser = browser_sessions[session_id]
        return BrowserInfoResponse(
            session_id=session_id,
            current_url=browser.driver.current_url,
            title=browser.driver.title
        )

    @app.post("/browser/navigate")
    def navigate(url: str, session_id: str = None):
        if not session_id and browser_sessions:
            session_id = list(browser_sessions.keys())[0]
        if session_id not in browser_sessions:
            raise HTTPException(status_code=404, detail="浏览器不存在")
        browser = browser_sessions[session_id]
        browser.driver.get(url)
        return {"status": "ok", "url": browser.driver.current_url}

    @app.get("/browser/screenshot")
    def take_screenshot(session_id: str = None):
        import base64
        if not session_id and browser_sessions:
            session_id = list(browser_sessions.keys())[0]
        if session_id not in browser_sessions:
            raise HTTPException(status_code=404, detail="浏览器不存在")
        browser = browser_sessions[session_id]
        screenshot = browser.driver.get_screenshot_as_png()
        b64 = base64.b64encode(screenshot).decode()
        return {"status": "ok", "image": f"data:image/png;base64,{b64}"}

    @app.get("/sessions")
    def list_sessions():
        return {"sessions": list(browser_sessions.keys()), "count": len(browser_sessions)}

    return app


# 导出应用
app = create_app()


# ========== 独立运行入口 ==========
if __name__ == "__main__":
    import uvicorn
    print("""
╔═══════════════════════════════════════════════════════════╗
║         my_spider Browser API 服务                     ║
║═══════════════════════════════════════════════════════════║
║  启动成功！访问以下地址：                              ║
║                                                           ║
║    http://localhost:8000/docs                            ║
║    http://localhost:8000/redoc                           ║
║                                                           ║
║  API 端点：                                             ║
║    POST /browser/create - 创建浏览器                    ║
║    POST /browser/close - 关闭浏览器                     ║
║    GET  /browser/info - 获取浏览器信息                 ║
║    GET  /browser/screenshot - 获取截图                 ║
║                                                           ║
║  停止服务：Ctrl + C                                     ║
╚═══════════════════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)