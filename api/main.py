"""
Competitor Intelligence Tracker — FastAPI Application Entry Point
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import domains, traffic, tech, sitemap, changes, keywords, scan

app = FastAPI(
    title="Competitor Intelligence Tracker API",
    description=(
        "API for SOHO's Competitor Intelligence module. "
        "All traffic data returned is ESTIMATED — not actual analytics."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": str(exc)},
    )


app.include_router(domains.router)
app.include_router(traffic.router)
app.include_router(tech.router)
app.include_router(sitemap.router)
app.include_router(changes.router)
app.include_router(keywords.router)
app.include_router(scan.router)


@app.get("/", tags=["health"])
async def root():
    return {
        "service": "Competitor Intelligence Tracker API",
        "version": "2.0.0",
        "status": "ok",
        "storage": "SQLite (local — data/tracker.db)",
        "disclaimer": "All traffic figures are estimates with ±7–11% variance.",
    }


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
