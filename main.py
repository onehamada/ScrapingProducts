from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from marketplace_scraper import (
    ARTIFACTS_DIR,
    CATEGORY_CHOICES,
    MarketplaceService,
    normalize_category_name,
)


ROOT_DIR = Path(__file__).resolve().parent
UI_FILE = ROOT_DIR / "ui.html"

app = FastAPI(
    title="Marketplace Search",
    description="Busca produtos na OLX, Mercado Livre, KaBuM e Terabyte com Selenium e interface web.",
    version="2.2.0",
)

service = MarketplaceService()
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACTS_DIR)), name="artifacts")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Termo para pesquisar")
    platforms: list[str] = Field(
        default_factory=lambda: ["olx", "mercadolivre"],
        description="Plataformas para pesquisar",
    )
    category: str = Field(
        default="auto",
        description="Categoria desejada: auto, placa-de-video, notebook, pc-completo ou processador",
    )
    max_results: int = Field(default=10, ge=1, le=30)
    headless: bool = Field(
        default=False,
        description="Executa o navegador sem janela. Menos confiavel para marketplaces.",
    )


def normalize_platforms(platforms: list[str] | None) -> list[str]:
    chosen = [platform.lower() for platform in (platforms or ["olx", "mercadolivre"])]
    available = set(service.available_platforms())
    invalid = [platform for platform in chosen if platform not in available]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Plataformas invalidas: {', '.join(invalid)}. Validas: {', '.join(sorted(available))}",
        )
    return chosen


def normalize_category(category: str | None) -> str:
    chosen = normalize_category_name(category)
    if chosen not in CATEGORY_CHOICES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Categoria invalida: {category}. "
                f"Validas: {', '.join(CATEGORY_CHOICES)}"
            ),
        )
    return chosen


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(UI_FILE)


@app.get("/api/info")
async def api_info() -> dict[str, object]:
    return {
        "name": "Marketplace Search",
        "version": "2.2.0",
        "platforms": service.available_platforms(),
        "categories": list(CATEGORY_CHOICES),
        "routes": {
            "ui": "/",
            "docs": "/docs",
            "health": "/api/health",
            "search": "/api/search",
            "olx": "/scrape/olx",
            "mercadolivre": "/scrape/mercadolivre",
            "kabum": "/scrape/kabum",
            "terabyte": "/scrape/terabyte",
            "facebook": "/scrape/facebook",
            "both": "/scrape/both",
        },
        "notes": [
            "OLX, Mercado Livre, KaBuM e Terabyte funcionam melhor com headless desativado.",
            "Buscas repetidas entram em cache curto para responder mais rapido.",
            "Consultas em varias plataformas agora rodam em paralelo.",
            "A categoria processador pode ser detectada automaticamente.",
            "Facebook Marketplace geralmente exige login e continua em modo beta.",
        ],
    }


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "message": "API pronta para pesquisa"}


@app.post("/api/search")
async def search_all(search_request: SearchRequest) -> dict[str, object]:
    platforms = normalize_platforms(search_request.platforms)
    category = normalize_category(search_request.category)
    return service.search_many(
        query=search_request.query,
        platforms=platforms,
        category=category,
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/olx")
async def scrape_olx_get(
    query: str = Query(..., min_length=2),
    category: str = Query("auto"),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_platform(
        "olx",
        query=query,
        category=normalize_category(category),
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/olx")
async def scrape_olx_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_platform(
        "olx",
        query=search_request.query,
        category=normalize_category(search_request.category),
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/mercadolivre")
async def scrape_mercadolivre_get(
    query: str = Query(..., min_length=2),
    category: str = Query("auto"),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_platform(
        "mercadolivre",
        query=query,
        category=normalize_category(category),
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/mercadolivre")
async def scrape_mercadolivre_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_platform(
        "mercadolivre",
        query=search_request.query,
        category=normalize_category(search_request.category),
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/facebook")
async def scrape_facebook_get(
    query: str = Query(..., min_length=2),
    category: str = Query("auto"),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_platform(
        "facebook",
        query=query,
        category=normalize_category(category),
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/facebook")
async def scrape_facebook_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_platform(
        "facebook",
        query=search_request.query,
        category=normalize_category(search_request.category),
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/kabum")
async def scrape_kabum_get(
    query: str = Query(..., min_length=2),
    category: str = Query("auto"),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_platform(
        "kabum",
        query=query,
        category=normalize_category(category),
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/kabum")
async def scrape_kabum_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_platform(
        "kabum",
        query=search_request.query,
        category=normalize_category(search_request.category),
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/terabyte")
async def scrape_terabyte_get(
    query: str = Query(..., min_length=2),
    category: str = Query("auto"),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_platform(
        "terabyte",
        query=query,
        category=normalize_category(category),
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/terabyte")
async def scrape_terabyte_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_platform(
        "terabyte",
        query=search_request.query,
        category=normalize_category(search_request.category),
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/both")
async def scrape_both_get(
    query: str = Query(..., min_length=2),
    category: str = Query("auto"),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_many(
        query=query,
        platforms=["olx", "mercadolivre"],
        category=normalize_category(category),
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/both")
async def scrape_both_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_many(
        query=search_request.query,
        platforms=["olx", "mercadolivre"],
        category=normalize_category(search_request.category),
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


def _open_browser() -> None:
    webbrowser.open("http://127.0.0.1:8000")


if __name__ == "__main__":
    threading.Timer(1.2, _open_browser).start()
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )
