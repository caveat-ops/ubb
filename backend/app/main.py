import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.limiter import limiter
from app.database import init_db
from app.routers import disciplines, graph, invites, posts, raw_posts, search, stats, sync

SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response: Response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(levelname)s:     %(name)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Universidade Bebê API",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(posts.router, prefix="/api/posts", tags=["posts"])
app.include_router(disciplines.router, prefix="/api/disciplines", tags=["disciplines"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
app.include_router(invites.router, prefix="/api/invites", tags=["invites"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(raw_posts.router, prefix="/api/raw-posts", tags=["raw-posts"])
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
    return {"available": True}


@app.get("/api/about")
async def about_info():
    url = settings.url_about
    # Extrai nome do path: linkedin.com/in/NOME/about/
    name = ""
    if "/in/" in url:
        name = url.split("/in/")[1].split("/")[0]
    return {"name": name, "url": url}
