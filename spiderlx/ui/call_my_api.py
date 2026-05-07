import requests
API_BASE_URL = "http://localhost:8000/api/v1/spider"


def call_spider_api(url: str, retype: str = 'text') -> dict:
    """调用爬虫 API"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/request",
            json={"url": url, "retype": retype},
            timeout=30
        )
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"status": "error", "detail": "API服务未启动，请先运行: uvicorn api.main:app --reload"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

