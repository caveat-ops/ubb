import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.routers import disciplines, graph, invites, posts, raw_posts, search, stats

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(levelname)s:     %(name)s - %(message)s",
)

try:
    import playwright  # noqa: F401
    from app.routers import sync
    HAS_SYNC = True
except ImportError:
    HAS_SYNC = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Universidade Bebê API",
    version="0.1.0",
    lifespan=lifespan,
)

origins = [
    o.strip()
    for o in settings.cors_origin.split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(posts.router, prefix="/api/posts", tags=["posts"])
app.include_router(disciplines.router, prefix="/api/disciplines", tags=["disciplines"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
app.include_router(invites.router, prefix="/api/invites", tags=["invites"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(raw_posts.router, prefix="/api/raw-posts", tags=["raw-posts"])
if HAS_SYNC:
    app.include_router(sync.router, prefix="/api/sync", tags=["sync"])


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=404, content={"detail": "Not found"})


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error"}
    )


@app.get("/")
async def root():
    return {"name": "Universidade Bebê API", "version": "0.1.0"}


@app.get("/api/sync-info")
async def sync_info():
    return {"available": HAS_SYNC}


@app.get("/api/about")
async def about_info():
    url = settings.url_about
    # Extrai nome do path: linkedin.com/in/NOME/about/
    name = ""
    if "/in/" in url:
        name = url.split("/in/")[1].split("/")[0]
    return {"name": name, "url": url}
