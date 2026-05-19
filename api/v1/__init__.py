from fastapi import APIRouter


def init_router():
    from api.v1.spider import save as spider_save

    router = APIRouter()
    router.include_router(spider_save.router, prefix="/save", tags=["save"])
    return router
