from __future__ import annotations

import argparse
import socket
import threading
import webbrowser

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from marketplace_scraper import (
    ARTIFACTS_DIR,
    MarketplaceService,
)
from marketplace_search.settings import (
    APP_DESCRIPTION,
    APP_NAME,
    APP_VERSION,
    ensure_runtime_directories,
    get_settings,
)


SETTINGS = ensure_runtime_directories(get_settings())

app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
)

service = MarketplaceService()
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACTS_DIR)), name="artifacts")
ACTIVE_SERVER = {"host": SETTINGS.host, "port": SETTINGS.port}


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Termo para pesquisar")
    platforms: list[str] = Field(
        default_factory=lambda: ["olx", "mercadolivre"],
        description="Plataformas para pesquisar",
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


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(SETTINGS.ui_file)


@app.get("/api/info")
async def api_info() -> dict[str, object]:
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "platforms": service.available_platforms(),
        "runtime": {
            "workspace_dir": str(SETTINGS.workspace_dir),
            "artifacts_dir": str(SETTINGS.artifacts_dir),
            "profiles_dir": str(SETTINGS.profile_root),
            "chrome_binary": str(SETTINGS.local_chrome) if SETTINGS.local_chrome.exists() else "",
            "browser_url": SETTINGS.browser_url(
                host=str(ACTIVE_SERVER["host"]),
                port=int(ACTIVE_SERVER["port"]),
            ),
        },
        "routes": {
            "ui": "/",
            "docs": "/docs",
            "health": "/api/health",
            "search": "/api/search",
            "olx": "/scrape/olx",
            "mercadolivre": "/scrape/mercadolivre",
            "kabum": "/scrape/kabum",
            "terabyte": "/scrape/terabyte",
            "pcgamerbrasilia": "/scrape/pcgamerbrasilia",
            "aliexpress": "/scrape/aliexpress",
            "facebook": "/scrape/facebook",
            "both": "/scrape/both",
        },
        "notes": [
            "OLX, Mercado Livre, KaBuM, Terabyte, PC Gamer Brasilia e AliExpress funcionam melhor com headless desativado.",
            "Buscas repetidas entram em cache curto para responder mais rapido.",
            "Consultas em varias plataformas rodam em paralelo.",
            "O perfil da busca e os filtros de hardware sao detectados automaticamente a partir da consulta.",
            "Facebook Marketplace pode retornar anuncios publicos sem login, mas algumas buscas podem exigir autenticacao.",
            "PC Gamer Brasilia usa navegador real porque o site bloqueia requisicoes diretas em algumas tentativas.",
            "AliExpress pode pedir captcha ou verificacao manual no navegador antes de liberar os resultados.",
            "Os resultados do AliExpress agora mostram avaliacao, origem do envio e a taxa de importacao do card quando ela vier destacada.",
            "Artefatos, cache e perfis agora vivem no workspace da aplicacao para manter o projeto mais independente.",
        ],
    }


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "message": "API pronta para pesquisa"}


@app.post("/api/search")
async def search_all(search_request: SearchRequest) -> dict[str, object]:
    platforms = normalize_platforms(search_request.platforms)
    return service.search_many(
        query=search_request.query,
        platforms=platforms,
        category="auto",
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/olx")
async def scrape_olx_get(
    query: str = Query(..., min_length=2),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_platform(
        "olx",
        query=query,
        category="auto",
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/olx")
async def scrape_olx_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_platform(
        "olx",
        query=search_request.query,
        category="auto",
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/mercadolivre")
async def scrape_mercadolivre_get(
    query: str = Query(..., min_length=2),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_platform(
        "mercadolivre",
        query=query,
        category="auto",
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/mercadolivre")
async def scrape_mercadolivre_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_platform(
        "mercadolivre",
        query=search_request.query,
        category="auto",
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/facebook")
async def scrape_facebook_get(
    query: str = Query(..., min_length=2),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_platform(
        "facebook",
        query=query,
        category="auto",
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/facebook")
async def scrape_facebook_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_platform(
        "facebook",
        query=search_request.query,
        category="auto",
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/kabum")
async def scrape_kabum_get(
    query: str = Query(..., min_length=2),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_platform(
        "kabum",
        query=query,
        category="auto",
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/kabum")
async def scrape_kabum_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_platform(
        "kabum",
        query=search_request.query,
        category="auto",
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/terabyte")
async def scrape_terabyte_get(
    query: str = Query(..., min_length=2),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_platform(
        "terabyte",
        query=query,
        category="auto",
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/terabyte")
async def scrape_terabyte_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_platform(
        "terabyte",
        query=search_request.query,
        category="auto",
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/pcgamerbrasilia")
async def scrape_pcgamerbrasilia_get(
    query: str = Query(..., min_length=2),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_platform(
        "pcgamerbrasilia",
        query=query,
        category="auto",
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/pcgamerbrasilia")
async def scrape_pcgamerbrasilia_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_platform(
        "pcgamerbrasilia",
        query=search_request.query,
        category="auto",
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/aliexpress")
async def scrape_aliexpress_get(
    query: str = Query(..., min_length=2),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_platform(
        "aliexpress",
        query=query,
        category="auto",
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/aliexpress")
async def scrape_aliexpress_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_platform(
        "aliexpress",
        query=search_request.query,
        category="auto",
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


@app.get("/scrape/both")
async def scrape_both_get(
    query: str = Query(..., min_length=2),
    max_results: int = Query(10, ge=1, le=30),
    headless: bool = Query(False),
) -> dict[str, object]:
    return service.search_many(
        query=query,
        platforms=["olx", "mercadolivre"],
        category="auto",
        max_results=max_results,
        headless=headless,
    )


@app.post("/scrape/both")
async def scrape_both_post(search_request: SearchRequest) -> dict[str, object]:
    return service.search_many(
        query=search_request.query,
        platforms=["olx", "mercadolivre"],
        category="auto",
        max_results=search_request.max_results,
        headless=search_request.headless,
    )


def _open_browser(host: str, port: int) -> None:
    webbrowser.open(SETTINGS.browser_url(host=host, port=port))


def _can_bind(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _resolve_port(host: str, requested_port: int, attempts: int = 20) -> int:
    if _can_bind(host, requested_port):
        return requested_port

    for candidate in range(requested_port + 1, requested_port + attempts + 1):
        if _can_bind(host, candidate):
            print(
                f"[startup] Porta {requested_port} ocupada. "
                f"Usando a porta {candidate}."
            )
            return candidate

    raise RuntimeError(
        f"Nenhuma porta livre encontrada a partir de {requested_port}."
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inicia o Marketplace Search como aplicacao local."
    )
    parser.add_argument(
        "--host",
        default=SETTINGS.host,
        help="Host para expor a API local.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=SETTINGS.port,
        help="Porta para expor a API local.",
    )
    browser_group = parser.add_mutually_exclusive_group()
    browser_group.add_argument(
        "--open-browser",
        dest="open_browser",
        action="store_true",
        help="Abre o navegador automaticamente.",
    )
    browser_group.add_argument(
        "--no-browser",
        dest="open_browser",
        action="store_false",
        help="Inicia o servidor sem abrir o navegador.",
    )
    parser.set_defaults(open_browser=SETTINGS.open_browser)
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Nivel de log do servidor.",
    )
    return parser.parse_args(argv)


def run_server(
    host: str,
    port: int,
    open_browser: bool,
    log_level: str = "info",
) -> int:
    resolved_port = _resolve_port(host, port)
    ACTIVE_SERVER["host"] = host
    ACTIVE_SERVER["port"] = resolved_port
    print(f"[startup] Marketplace Search em {SETTINGS.browser_url(host=host, port=resolved_port)}")

    if open_browser:
        threading.Timer(
            SETTINGS.browser_open_delay_seconds,
            _open_browser,
            args=[host, resolved_port],
        ).start()

    uvicorn.run(
        app,
        host=host,
        port=resolved_port,
        reload=False,
        log_level=log_level,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_server(
        host=args.host,
        port=args.port,
        open_browser=args.open_browser,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    raise SystemExit(main())
