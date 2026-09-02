from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.session import Base, engine
from app.routers import chat, usage


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="LLM API Gateway", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(chat.router, prefix="/v1")
app.include_router(usage.router, prefix="/v1")
