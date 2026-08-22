"""FastAPI application entry point.

Run with:  uvicorn app.main:app --reload
Docs at:   http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import notes, options, render
from app.render.fonts import load_fonts

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register fonts once at startup rather than on the first request, so no
    # user pays the TTF parsing cost.
    load_fonts()
    yield


app = FastAPI(title="Handwritten Notes API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes.router, prefix=API_PREFIX)
app.include_router(options.router, prefix=API_PREFIX)
app.include_router(render.router, prefix=API_PREFIX)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
