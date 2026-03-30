from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


APP_NAME = "Marketplace Search"
APP_VERSION = "2.7.0"
APP_DESCRIPTION = (
    "Busca produtos na OLX, Mercado Livre, KaBuM, Terabyte, "
    "PC Gamer Brasilia, AliExpress e Facebook com Selenium, "
    "interface web e radar de oportunidades."
)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        if not key:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def _env_path(name: str) -> Path | None:
    raw_value = os.getenv(name, "").strip()
    return Path(raw_value).expanduser() if raw_value else None


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"", "0", "false", "no", "off"}


def _env_int(name: str, default: int, minimum: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value >= minimum else default


def _env_float(name: str, default: float, minimum: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        return default
    return value if value >= minimum else default


def _default_workspace_dir() -> Path:
    explicit = _env_path("MARKETPLACE_HOME")
    if explicit is not None:
        return explicit

    if os.name == "nt":
        local_appdata = os.getenv("LOCALAPPDATA", "").strip()
        if local_appdata:
            return Path(local_appdata) / "MarketplaceSearch"

    return Path.home() / ".marketplace-search"


def _default_local_chrome_name() -> str:
    return "chrome.exe" if os.name == "nt" else "chrome"


def _first_existing_path(paths: list[Path | None]) -> Path | None:
    for path in paths:
        if path is not None and path.exists():
            return path
    return None


@dataclass(frozen=True)
class AppSettings:
    app_name: str
    version: str
    description: str
    code_root: Path
    package_root: Path
    ui_file: Path
    workspace_dir: Path
    artifacts_dir: Path
    artifacts_html_dir: Path
    artifacts_json_dir: Path
    profile_root: Path
    launcher_state_dir: Path
    local_chrome: Path
    host: str
    port: int
    open_browser: bool
    browser_open_delay_seconds: float
    cache_ttl_seconds: int
    cache_max_entries: int
    save_success_html_snapshots: bool
    save_success_json_snapshots: bool
    import_tax_fallback_percent: float
    facebook_region_slug: str

    def browser_url(self, host: str | None = None, port: int | None = None) -> str:
        browser_host = host or self.host
        if browser_host in {"0.0.0.0", "::", "[::]"}:
            browser_host = "127.0.0.1"
        return f"http://{browser_host}:{port or self.port}"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    code_root = Path(__file__).resolve().parent.parent
    package_root = Path(__file__).resolve().parent

    _load_dotenv(Path.cwd() / ".env")
    workspace_dir = _default_workspace_dir()
    _load_dotenv(workspace_dir / ".env")
    workspace_dir = _default_workspace_dir()

    artifacts_dir = _env_path("MARKETPLACE_ARTIFACTS_DIR") or workspace_dir / "artifacts"
    profile_root = _env_path("MARKETPLACE_PROFILE_DIR") or workspace_dir / "profiles"
    launcher_state_dir = _env_path("MARKETPLACE_STATE_DIR") or workspace_dir / "launcher"

    chrome_name = _default_local_chrome_name()
    explicit_chrome = _env_path("MARKETPLACE_CHROME_BINARY")
    local_chrome = explicit_chrome or _first_existing_path(
        [
            workspace_dir / "chrome-win64" / chrome_name,
            code_root / "chrome-win64" / chrome_name,
        ]
    )
    if local_chrome is None:
        local_chrome = workspace_dir / "chrome-win64" / chrome_name

    return AppSettings(
        app_name=APP_NAME,
        version=APP_VERSION,
        description=APP_DESCRIPTION,
        code_root=code_root,
        package_root=package_root,
        ui_file=package_root / "ui.html",
        workspace_dir=workspace_dir,
        artifacts_dir=artifacts_dir,
        artifacts_html_dir=artifacts_dir / "html",
        artifacts_json_dir=artifacts_dir / "json",
        profile_root=profile_root,
        launcher_state_dir=launcher_state_dir,
        local_chrome=local_chrome,
        host=os.getenv("MARKETPLACE_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=_env_int("MARKETPLACE_PORT", 8000, minimum=1),
        open_browser=_env_bool("MARKETPLACE_OPEN_BROWSER", True),
        browser_open_delay_seconds=_env_float("MARKETPLACE_BROWSER_DELAY", 1.2, minimum=0.0),
        cache_ttl_seconds=_env_int("MARKETPLACE_CACHE_TTL_SECONDS", 120, minimum=1),
        cache_max_entries=_env_int("MARKETPLACE_CACHE_MAX_ENTRIES", 96, minimum=1),
        save_success_html_snapshots=_env_bool(
            "MARKETPLACE_SAVE_SUCCESS_HTML_SNAPSHOTS",
            False,
        ),
        save_success_json_snapshots=_env_bool(
            "MARKETPLACE_SAVE_SUCCESS_JSON_SNAPSHOTS",
            True,
        ),
        import_tax_fallback_percent=_env_float(
            "MARKETPLACE_IMPORT_TAX_FALLBACK_PERCENT",
            45.0,
            minimum=0.0,
        ),
        facebook_region_slug=os.getenv("MARKETPLACE_FACEBOOK_REGION_SLUG", "saopaulo").strip() or "saopaulo",
    )


def ensure_runtime_directories(settings: AppSettings | None = None) -> AppSettings:
    current = settings or get_settings()
    for path in (
        current.workspace_dir,
        current.artifacts_html_dir,
        current.artifacts_json_dir,
        current.profile_root,
        current.launcher_state_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    return current
