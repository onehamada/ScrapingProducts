from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import unicodedata
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from html import unescape as html_unescape
from pathlib import Path
from statistics import mean, median
from typing import Any
from urllib.parse import quote_plus, unquote, urljoin

from bs4 import BeautifulSoup, SoupStrainer
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.chrome.options import Options

from marketplace_search.settings import get_settings

SETTINGS = get_settings()
ROOT_DIR = SETTINGS.code_root
ARTIFACTS_DIR = SETTINGS.artifacts_dir
ARTIFACTS_HTML_DIR = SETTINGS.artifacts_html_dir
ARTIFACTS_JSON_DIR = SETTINGS.artifacts_json_dir
PROFILE_ROOT = SETTINGS.profile_root
LOCAL_CHROME = SETTINGS.local_chrome
FACEBOOK_DEFAULT_REGION_SLUG = "saopaulo"
ALIEXPRESS_BASE_URL = "https://pt.aliexpress.com"
PC_GAMER_BRASILIA_BASE_URL = "https://www.pcgamerbrasilia.com.br"
PROFILE_LOCK_FILES = (
    "SingletonCookie",
    "SingletonLock",
    "SingletonSocket",
    "lockfile",
)

R_CURRENCY = re.compile(r"R\$\s*[\d\.\,]+")
R_HTML_TAG = re.compile(r"<[^>]+>")
R_WHITESPACE = re.compile(r"\s+")
R_TOKEN = re.compile(r"[a-z0-9]+")
R_MEMORY_SIZE = re.compile(r"\b\d{1,3}\s*gb\b")
R_XEON_MODEL = re.compile(r"\bxeon\s*(e[357])?\s*[- ]?(\d{4})\s*(v\d+)?\b")
R_XEON_MODEL_FAMILY = re.compile(r"\b(e[357])\s*[- ]?(\d{4})\s*(v\d+)?\b")
R_INTEL_CORE_MODEL = re.compile(r"\b(?:core\s*)?i[3579]\s*[- ]?\d{3,5}[a-z]{0,2}\b")
R_RYZEN_MODEL = re.compile(r"\bryzen\s*(?:[3579]\s*)?\d{3,5}[a-z]{0,3}\b")
R_EPYC_MODEL = re.compile(r"\bepyc\s*\d{3,4}\b")
R_MOTHERBOARD_CHIPSET = re.compile(r"\b(?:a|b|h|x|z)\d{2,3}[a-z]{0,2}\b")
R_POWER_WATTAGE = re.compile(r"\b\d{2,4}\s*w\b", re.IGNORECASE)
R_MEMORY_SPEED = re.compile(r"\b\d{3,5}\s*mhz\b", re.IGNORECASE)
R_DISPLAY_SIZE_LOOSE = re.compile(r"\b(\d{1,2}(?:[.,]\d{1,2})?)\b")
R_DISPLAY_SIZE = re.compile(
    r"\b(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:[\"“”″]|''|pol(?:egadas?)?)(?=\D|$)",
    re.IGNORECASE,
)

R_FACEBOOK_LOGIN_INPUT = re.compile(
    r"<input[^>]+(?:name|id)\s*=\s*[\"']email[\"']",
    re.IGNORECASE,
)
R_ALIEXPRESS_ITEM_HREF = re.compile(
    r'href="([^"]*(?:item|i)/(\d+)\.(?:html|htm)[^"]*)"',
    re.IGNORECASE,
)
R_ALIEXPRESS_DETAIL_TAX_HTML = re.compile(
    r"(R\$\s*[\d\.\,]+)(?:\s|&nbsp;|<[^>]+>)*\+?(?:\s|&nbsp;|<[^>]+>)*"
    r"(?:em\s+impostos\s+estimados|in\s+estimated\s+tax(?:es)?)",
    re.IGNORECASE,
)
R_ALIEXPRESS_DETAIL_TAX_TEXT = re.compile(
    r"(R\$\s*[\d\.\,]+)\+?\s*(?:em impostos estimados|in estimated tax(?:es)?)",
    re.IGNORECASE,
)
R_NEXT_DATA_SCRIPT = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)

ALIEXPRESS_SHIP_FROM_LABELS = {
    "BR": "Brasil",
    "CN": "China",
    "ES": "Espanha",
    "FR": "Franca",
    "IT": "Italia",
    "MX": "Mexico",
    "PL": "Polonia",
    "PT": "Portugal",
    "RU": "Russia",
    "TR": "Turquia",
    "US": "Estados Unidos",
}

STOPWORDS = {
    "a",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "por",
    "sem",
    "um",
    "uma",
}

QUERY_NOISE_TOKENS = {
    "computador",
    "cpu",
    "desktop",
    "laptop",
    "notebook",
    "pc",
    "placa",
    "processador",
    "video",
}

DISPLAY_QUERY_TERMS = (
    "monitor",
    "monitores",
    "display",
    "ultrawide",
)

INCH_UNIT_TERMS = (
    "pol",
    "polegada",
    "polegadas",
)

DISPLAY_SIZE_TOLERANCE = 0.7

DISPLAY_HINT_TERMS = (
    "fhd",
    "full hd",
    "gaming monitor",
    "hz",
    "ips",
    "led monitor",
    "monitor gamer",
    "oled",
    "qhd",
    "quad hd",
    "tela gamer",
    "tn",
    "uhd",
    "ultrawide",
    "va",
    "wqhd",
)

TOKEN_CANONICAL_ALIASES = {
    "desbl": "desbloqueado",
    "desbloq": "desbloqueado",
    "nintedo": "nintendo",
    "nintento": "nintendo",
    "nitendo": "nintendo",
    "swite": "switch",
    "swith": "switch",
}

TITLE_BLOCK_TERMS = (
    "defeito",
    "defeituoso",
    "defeituosa",
    "com defeito",
    "queimado",
    "queimada",
    "sucata",
    "retirar pecas",
    "retirada de pecas",
    "sem funcionar",
    "nao funciona",
    "não funciona",
)

BUNDLE_TERMS = (
    "pc gamer",
    "computador",
    "desktop",
    "notebook",
    "setup",
    "kit",
    "gabinete",
    "completo",
    "cpu ",
    " cpu",
)

GPU_GENERIC_CONTEXT_TERMS = (
    "computador",
    "desktop",
    "cpu ",
    " cpu",
)

GPU_STRICT_BUNDLE_TERMS = tuple(
    term for term in BUNDLE_TERMS if term not in GPU_GENERIC_CONTEXT_TERMS
)

GPU_QUERY_TERMS = (
    "gtx",
    "rtx",
    "rx",
    "geforce",
    "radeon",
    "gpu",
    "placa de video",
    "placa de video",
)

GPU_SEARCH_NOISE_TERMS = (
    "amd",
    "geforce",
    "gpu",
    "nvidia",
    "placa de video",
    "placa grafica",
    "radeon",
)

GPU_FAMILY_TERMS = (
    "amd",
    "arc",
    "geforce",
    "gtx",
    "nvidia",
    "quadro",
    "radeon",
    "rtx",
    "rx",
)

GPU_VARIANT_TERMS = (
    "ti",
    "super",
    "xt",
    "xtx",
    "mobile",
)

SYSTEM_SPEC_TERMS = (
    "xeon",
    "ryzen",
    "i3",
    "i5",
    "i7",
    "i9",
    "intel core",
    "processador",
    "ram",
    "ddr3",
    "ddr4",
    "ddr5",
    "ssd",
    "nvme",
    "hdd",
    "monitor",
)

NOTEBOOK_TERMS = (
    "notebook",
    "laptop",
)

PROCESSOR_QUERY_TERMS = (
    "athlon",
    "celeron",
    "epyc",
    "pentium",
    "processador",
    "ryzen",
    "sempron",
    "threadripper",
    "xeon",
)

PROCESSOR_BUNDLE_QUERY_TERMS = (
    "combo",
    "kit",
    "motherboard",
    "placa mae",
    "upgrade",
)

PROCESSOR_SEARCH_NOISE_TERMS = (
    "amd",
    "cpu",
    "intel",
    "processador",
)

PC_TERMS = (
    "pc gamer",
    "pc completo",
    "computador",
    "desktop",
    "setup",
    "all in one",
    "cpu ",
    " cpu",
)

MEMORY_QUERY_TERMS = (
    "memoria",
    "memoria ram",
    "ram",
    "ddr3",
    "ddr4",
    "ddr5",
    "sodimm",
    "so dimm",
    "so-dimm",
)

MEMORY_SEARCH_NOISE_TERMS = (
    "memoria",
    "memoria ram",
    "ram",
)

MOTHERBOARD_QUERY_TERMS = (
    "placa mae",
    "motherboard",
    "mainboard",
    "mobo",
)

MOTHERBOARD_SEARCH_NOISE_TERMS = (
    "placa mae",
    "motherboard",
    "mainboard",
    "mobo",
)

MOTHERBOARD_SOCKET_TERMS = (
    "am4",
    "am5",
    "fm2",
    "lga 1151",
    "lga 1200",
    "lga 1700",
    "s1700",
)

POWER_SUPPLY_QUERY_TERMS = (
    "fonte",
    "psu",
    "80 plus",
    "80plus",
)

POWER_SUPPLY_SEARCH_NOISE_TERMS = (
    "fonte",
    "psu",
)

POWER_SUPPLY_HINT_TERMS = (
    "bronze",
    "gold",
    "modular",
    "platinum",
    "semi modular",
    "semimodular",
)

POWER_SUPPLY_ACCESSORY_TERMS = (
    "adaptador",
    "carregador",
    "fonte notebook",
    "fonte para notebook",
)

CASE_QUERY_TERMS = (
    "gabinete",
    "case",
    "mid tower",
    "mini tower",
    "full tower",
)

CASE_SEARCH_NOISE_TERMS = (
    "gabinete",
    "case",
)

COOLER_QUERY_TERMS = (
    "water cooler",
    "air cooler",
    "aircooler",
    "cooler cpu",
    "cooler",
)

COOLER_SEARCH_NOISE_TERMS = (
    "cooler",
)

XEON_PLATFORM_TERMS = (
    "x58",
    "x79",
    "x99",
)

XEON_BUNDLE_TERMS = (
    "kit",
    "combo",
    "placa mae",
    "motherboard",
    "memoria",
    "memoria ram",
    "ddr3",
    "ddr4",
    "ddr5",
    "cooler",
    "water cooler",
    "gabinete",
    "fonte",
    "hd ",
    " hd",
    "ssd",
    "nvme",
    "wifi",
    "windows",
    "x79",
    "x99",
    "x58",
    "supermicro",
    "workstation",
)

PROCESSOR_BUNDLE_TERMS = (
    "kit",
    "combo",
    "placa mae",
    "motherboard",
    "memoria",
    "memoria ram",
    "ddr3",
    "ddr4",
    "ddr5",
    "cooler",
    "water cooler",
    "gabinete",
    "fonte",
    "hd ",
    " hd",
    "ssd",
    "nvme",
    "wifi",
    "windows",
    "gpu",
    "placa de video",
)

PROCESSOR_ACCESSORY_TERMS = (
    "adaptador",
    "bracket",
    "dissipador",
    "fan",
    "suporte",
)

SERVER_OEM_TERMS = (
    "ibm",
    "dell",
    "hp",
    "lenovo",
    "poweredge",
    "proliant",
    "thinkserver",
    "rd430",
    "r320",
    "r420",
    "r520",
    "t320",
    "dl360e",
    "dl380e",
    "ml350e",
    "g8",
    "g9",
)

GPU_ACCESSORY_TERMS = (
    "fonte",
    "water cooler",
    "cooler",
    "fan",
    "teclado",
    "mouse",
    "suporte",
    "cabo",
    "adaptador",
    "placa mae",
    "motherboard",
    "memoria",
    "memoria ram",
    "carregador",
)

MOTHERBOARD_BUNDLE_TERMS = (
    "kit",
    "combo",
    "processador",
    "memoria",
    "memoria ram",
    "ddr3",
    "ddr4",
    "ddr5",
    "ssd",
    "nvme",
    "fonte",
    "gabinete",
    "placa de video",
)

FACEBOOK_OPTIONAL_QUERY_TOKENS = {
    "bloqueado",
    "bloqueada",
    "desbloqueado",
    "desbloqueada",
    "novo",
    "novissimo",
    "seminovo",
}

FACEBOOK_CONSOLE_ACCESSORY_TERMS = (
    "joy con",
    "joy-con",
    "acessorio",
    "acessorios",
    "adaptador",
    "capa",
    "carregador",
    "case",
    "controle",
    "dock",
    "grip",
    "jogo",
    "jogos",
    "pelicula",
    "suporte",
)

SWITCH_UNLOCK_QUERY_TERMS = (
    "bloqueado",
    "bloqueada",
    "desbloqueado",
    "desbloqueada",
    "destravado",
    "destravada",
    "modificado",
    "modificada",
)

SWITCH_POSITIVE_UNLOCK_TERMS = (
    "desbloqueado",
    "desbloqueada",
    "destravado",
    "destravada",
    "modificado",
    "modificada",
)

SWITCH_QUERY_NOISE_TERMS = {
    "con",
    "controle",
    "joy",
    "joycon",
}

SWITCH_SERVICE_TERMS = (
    "destrava",
    "destravar",
    "desbloqueio",
    "desbloquear",
    "faço destrava",
    "faco destrava",
    "faço desbloqueio",
    "faco desbloqueio",
    "instalacao",
    "instalação",
    "servico",
    "serviço",
)

CATEGORY_CHOICES = (
    "auto",
    "placa-de-video",
    "notebook",
    "pc-completo",
    "processador",
    "monitor",
    "memoria",
    "armazenamento",
    "placa-mae",
    "fonte",
    "gabinete",
    "cooler",
)

CATEGORY_ALIASES = {
    "auto": "auto",
    "gpu": "placa-de-video",
    "placa": "placa-de-video",
    "placa de video": "placa-de-video",
    "notebook": "notebook",
    "laptop": "notebook",
    "pc": "pc-completo",
    "pc gamer": "pc-completo",
    "pc completo": "pc-completo",
    "desktop": "pc-completo",
    "processador": "processador",
    "cpu": "processador",
    "monitor": "monitor",
    "display": "monitor",
    "memoria": "memoria",
    "memoria ram": "memoria",
    "ram": "memoria",
    "armazenamento": "armazenamento",
    "ssd": "armazenamento",
    "hdd": "armazenamento",
    "placa mae": "placa-mae",
    "motherboard": "placa-mae",
    "fonte": "fonte",
    "psu": "fonte",
    "gabinete": "gabinete",
    "case": "gabinete",
    "cooler": "cooler",
    "water cooler": "cooler",
}

SEARCH_CACHE_TTL_SECONDS = SETTINGS.cache_ttl_seconds
SEARCH_CACHE_MAX_ENTRIES = SETTINGS.cache_max_entries
SEARCH_FALLBACK_MAX_ATTEMPTS = 3
EARLY_SUCCESS_TARGET_PLATFORMS = frozenset({"kabum", "terabyte", "pcgamerbrasilia"})


def repair_mojibake(value: str) -> str:
    text = value or ""
    if not text or not any(marker in text for marker in ("Ã", "Â", "â€", "â€™", "â€œ", "â€")):
        return text
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    return repaired


@lru_cache(maxsize=32768)
def normalize_text(value: str) -> str:
    return R_WHITESPACE.sub(" ", repair_mojibake(value or "")).strip()


@lru_cache(maxsize=32768)
def normalize_match_text(value: str) -> str:
    ascii_text = (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return normalize_text(re.sub(r"[^a-z0-9]+", " ", ascii_text))


def summarize_webdriver_message(error: Exception | str) -> str:
    message = normalize_text(str(error))
    if not message:
        return ""

    message = re.split(r"stacktrace:", message, maxsplit=1, flags=re.IGNORECASE)[0]
    message = re.sub(r"^message:\s*", "", message, flags=re.IGNORECASE).strip()
    message = re.sub(r"\(session info:[^)]+\)", "", message, flags=re.IGNORECASE).strip()
    return normalize_text(message.rstrip(":"))


@lru_cache(maxsize=32768)
def compact_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_match_text(value))


@lru_cache(maxsize=32768)
def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_match_text(value)).strip("-")
    return slug or "busca"


def first_matching_text(nodes: list[Any], pattern: re.Pattern[str] | None = None) -> str:
    for node in nodes:
        text = normalize_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if pattern and not pattern.search(text):
            continue
        return text
    return ""


def format_brl(fraction: str, cents: str = "") -> str:
    if not fraction:
        return ""
    return f"R$ {fraction}" if not cents else f"R$ {fraction},{cents}"


def format_brl_value(value: float | int | None) -> str:
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


@lru_cache(maxsize=32768)
def parse_price_value(text: str | None) -> float | None:
    match = R_CURRENCY.search(text or "")
    if not match:
        return None

    raw = match.group(0).replace("R$", "").strip()
    if not raw:
        return None

    normalized = raw.replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def extract_balanced_json_block(
    text: str,
    start_index: int,
    opener: str = "[",
    closer: str = "]",
) -> str | None:
    if start_index < 0 or start_index >= len(text) or text[start_index] != opener:
        return None

    depth = 0
    in_string = False
    escape = False

    for index in range(start_index, len(text)):
        char = text[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]

    return None


def extract_json_array_after_marker(
    text: str,
    marker: str,
) -> list[dict[str, Any]]:
    marker_index = text.find(marker)
    if marker_index < 0:
        return []

    start_index = marker_index + len(marker)
    payload = extract_balanced_json_block(text, start_index, opener="[", closer="]")
    if not payload:
        return []

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return []

    return [item for item in parsed if isinstance(item, dict)]


def parse_optional_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_rating_value(value: Any) -> float | None:
    rating = parse_optional_float(value)
    if rating is None or rating <= 0 or rating > 5:
        return None
    return round(rating, 1)


def parse_optional_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def format_percent_value(value: float | int | None) -> str:
    number = parse_optional_float(value)
    if number is None:
        return ""
    if number.is_integer():
        return f"{int(number)}%"
    return f"{number:.1f}".replace(".", ",") + "%"


@lru_cache(maxsize=32768)
def parse_aliexpress_trace_payload(value: str) -> dict[str, Any]:
    decoded = html_unescape(unquote(value or ""))
    if not decoded:
        return {}

    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def normalize_aliexpress_ship_from(code: str) -> str:
    normalized = normalize_match_text(code).upper()
    return re.sub(r"[^A-Z]", "", normalized)[:2]


def aliexpress_ship_from_label(code: str) -> str:
    normalized = normalize_aliexpress_ship_from(code)
    if not normalized:
        return ""
    return ALIEXPRESS_SHIP_FROM_LABELS.get(normalized, normalized)


def aliexpress_shipping_origin_label(code: str) -> str:
    normalized = normalize_aliexpress_ship_from(code)
    if not normalized:
        return ""
    if normalized == "BR":
        return "Do Brasil"
    country = aliexpress_ship_from_label(normalized)
    return f"Importado de {country}"


def is_missing_import_tax_label(value: str) -> bool:
    normalized = normalize_text(value).strip().lower()
    return normalized in {
        "",
        "nao informado pelo aliexpress",
        "nao foi possivel ler a taxa",
        "nao verificada nesta rodada",
    }


def has_aliexpress_local_flag(raw_item: dict[str, Any]) -> bool:
    selling_points = (
        raw_item.get("sellingPoints")
        if isinstance(raw_item.get("sellingPoints"), list)
        else []
    )
    for point in selling_points:
        if not isinstance(point, dict):
            continue
        source = normalize_text(str(point.get("source", ""))).lower()
        tag_content = point.get("tagContent", {}) if isinstance(point.get("tagContent"), dict) else {}
        tag_text = normalize_match_text(str(tag_content.get("tagText", "")))
        if source == "local_flag":
            return True
        if any(
            marker in tag_text
            for marker in ("product in brazil", "produto no brasil", "ship from brazil", "do brasil")
        ):
            return True
    return False


@lru_cache(maxsize=32768)
def normalize_unit_aliases(value: str) -> str:
    normalized = repair_mojibake(value or "")
    if not normalized:
        return ""

    # Normalize inch markers so queries like `24 polegadas` also match titles like
    # `24"`, `24''` or `24 Pol`.
    normalized = re.sub(
        R_DISPLAY_SIZE,
        r"\1 pol",
        normalized,
    )
    normalized = re.sub(r"\bpolegadas?\b", "pol", normalized, flags=re.IGNORECASE)
    return normalized


@lru_cache(maxsize=32768)
def extract_display_sizes(value: str) -> tuple[float, ...]:
    sizes: list[float] = []
    normalized_value = repair_mojibake(value or "")

    for raw_size in R_DISPLAY_SIZE.findall(normalized_value):
        try:
            sizes.append(float(raw_size.replace(",", ".")))
        except ValueError:
            continue

    for raw_size in R_DISPLAY_SIZE_LOOSE.findall(normalized_value):
        try:
            size = float(raw_size.replace(",", "."))
        except ValueError:
            continue
        if size < 10 or size > 60 or size in sizes:
            continue
        sizes.append(size)
    return tuple(sizes)


def display_size_query_tokens(query: str) -> set[str]:
    tokens: set[str] = set(INCH_UNIT_TERMS)
    for match in R_DISPLAY_SIZE.finditer(repair_mojibake(query or "")):
        tokens.update(match_tokens(match.group(0)))
    return tokens


@lru_cache(maxsize=32768)
def match_tokens(value: str) -> tuple[str, ...]:
    expanded = normalize_match_text(normalize_unit_aliases(value))
    expanded = re.sub(r"\b(\d{1,3})\s*g\b", r"\1 gb", expanded)
    expanded = re.sub(r"([a-z])([0-9])", r"\1 \2", expanded)
    expanded = re.sub(r"([0-9])([a-z])", r"\1 \2", expanded)
    tokens = []
    for token in R_TOKEN.findall(expanded):
        token = TOKEN_CANONICAL_ALIASES.get(token, token)
        if token in STOPWORDS:
            continue
        if token not in tokens:
            tokens.append(token)
    return tuple(tokens)


@lru_cache(maxsize=8192)
def query_tokens(query: str) -> tuple[str, ...]:
    return tuple(token for token in match_tokens(query) if token not in QUERY_NOISE_TOKENS)


@lru_cache(maxsize=8192)
def normalize_search_query_text(query: str) -> str:
    normalized = normalize_match_text(query)
    if not normalized:
        return ""

    normalized = re.sub(r"\b(\d{1,3})\s*g\b", r"\1 gb", normalized)
    for source, target in TOKEN_CANONICAL_ALIASES.items():
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)
    return normalize_text(normalized)


def replace_query_terms(query: str, replacements: dict[str, str]) -> str:
    normalized = normalize_match_text(query)
    if not normalized:
        return ""

    for source, target in replacements.items():
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)
    return normalize_text(normalized)


def is_switch_console_query(query: str) -> bool:
    tokens = set(query_tokens(query))
    if "switch" not in tokens:
        return False
    return not any(token in tokens for token in SWITCH_QUERY_NOISE_TERMS)


def has_match_term(normalized_value: str, tokens: set[str], term: str) -> bool:
    normalized_term = normalize_match_text(term)
    if not normalized_term:
        return False
    if " " in normalized_term:
        return f" {normalized_term} " in f" {normalized_value} "
    term_tokens = match_tokens(normalized_term)
    return bool(term_tokens) and all(token in tokens for token in term_tokens)


def has_any_match_term(normalized_value: str, tokens: set[str], terms: tuple[str, ...]) -> bool:
    return any(has_match_term(normalized_value, tokens, term) for term in terms)


def is_xeon_query(query: str) -> bool:
    return "xeon" in normalize_match_text(query)


def is_processor_query(query: str) -> bool:
    query_match = normalize_match_text(query)
    return (
        is_xeon_query(query)
        or any(term in query_match for term in PROCESSOR_QUERY_TERMS)
        or R_INTEL_CORE_MODEL.search(query_match) is not None
        or R_RYZEN_MODEL.search(query_match) is not None
        or R_EPYC_MODEL.search(query_match) is not None
    )


def extract_xeon_signature(value: str) -> tuple[str, str, str] | None:
    normalized = normalize_match_text(value)
    match = R_XEON_MODEL.search(normalized)
    if not match:
        match = R_XEON_MODEL_FAMILY.search(normalized)
    if not match:
        return None
    family, model, version = match.groups()
    return (family or "", model or "", version or "")


def has_xeon_model_match(query: str, title: str) -> bool:
    if not is_xeon_query(query):
        return False

    query_signature = extract_xeon_signature(query)
    title_signature = extract_xeon_signature(title)
    if not query_signature or not title_signature:
        return False

    query_family, query_model, query_version = query_signature
    title_family, title_model, title_version = title_signature

    if query_model != title_model:
        return False
    if query_version and query_version != title_version:
        return False
    if query_family and title_family and query_family != title_family:
        return False
    return True


def has_xeon_bundle_mismatch(query: str, title: str) -> bool:
    if not is_xeon_query(query):
        return False

    if has_processor_bundle_mismatch(query, title):
        return True

    query_match = normalize_match_text(query)
    title_match = normalize_match_text(title)
    title_tokens = set(match_tokens(title))

    if any(term in title_match and term not in query_match for term in PC_TERMS):
        return True
    if is_xeon_bundle_query(query):
        if has_processor_accessory_mismatch(query, title):
            return True
        if "dual" in title_tokens and "dual" not in query_tokens(query):
            return True
        return False
    if any(term in title_match and term not in query_match for term in XEON_BUNDLE_TERMS):
        return True
    if "dual" in title_tokens and "dual" not in query_tokens(query):
        return True
    if R_MEMORY_SIZE.search(title_match) and not R_MEMORY_SIZE.search(query_match):
        return True
    return False


def has_processor_bundle_mismatch(query: str, title: str) -> bool:
    if not is_processor_query(query):
        return False

    query_match = normalize_match_text(query)
    title_match = normalize_match_text(title)

    if any(term in title_match and term not in query_match for term in PC_TERMS):
        return True
    if any(term in title_match and term not in query_match for term in NOTEBOOK_TERMS):
        return True
    if is_processor_bundle_query(query):
        return False
    if any(term in title_match and term not in query_match for term in PROCESSOR_BUNDLE_TERMS):
        return True
    return False


def has_server_oem_mismatch(query: str, title: str) -> bool:
    if not is_processor_query(query):
        return False

    query_match = normalize_match_text(query)
    title_match = normalize_match_text(title)
    if "servidor" in query_match or "server" in query_match:
        return False

    if "processador para servidor" in title_match:
        return True
    if any(term in title_match and term not in query_match for term in SERVER_OEM_TERMS):
        return True
    return False


def has_untested_terms(title: str) -> bool:
    title_match = normalize_match_text(title)
    return any(
        term in title_match
        for term in ("sem teste", "s teste", "no estado", "nao testado")
    )


def sort_items_for_query(query: str, items: list["Listing"]) -> list["Listing"]:
    def price_key(item: "Listing") -> float:
        effective_price = listing_effective_price_value(item)
        return effective_price if effective_price is not None else float("inf")

    def exact_title_match(item: "Listing") -> bool:
        return title_contains_query(query, item.title)

    return sorted(
        items,
        key=lambda item: (
            price_key(item) == float("inf"),
            price_key(item),
            not exact_title_match(item),
            len(item.title),
        ),
    )


def build_xeon_search_query(query: str) -> str:
    signature = extract_xeon_signature(query)
    if not signature:
        return query

    family, model, _version = signature
    parts = ["xeon"]
    if family:
        parts.append(family)
    parts.append(model)
    return " ".join(parts)


def is_processor_bundle_query(query: str) -> bool:
    if not is_processor_query(query):
        return False

    query_match = normalize_match_text(query)
    return any(term in query_match for term in PROCESSOR_BUNDLE_QUERY_TERMS)


def is_xeon_bundle_query(query: str) -> bool:
    if not is_xeon_query(query):
        return False

    query_match = normalize_match_text(query)
    if any(term in query_match for term in PROCESSOR_BUNDLE_QUERY_TERMS):
        return True
    return any(term in query_match for term in XEON_PLATFORM_TERMS)


def has_memory_facet(value: str) -> bool:
    normalized = normalize_match_text(value)
    return (
        R_MEMORY_SPEED.search(normalized) is not None
        or any(term in normalized for term in MEMORY_QUERY_TERMS)
    )


def has_storage_facet(value: str) -> bool:
    normalized = normalize_match_text(value)
    return any(term in normalized for term in ("hdd", "nvme", "sata", "ssd", "m 2", "m2", "hd "))


def has_monitor_facet(value: str) -> bool:
    normalized = normalize_match_text(value)
    tokens = set(match_tokens(value))
    return has_any_match_term(normalized, tokens, DISPLAY_QUERY_TERMS) or (
        bool(extract_display_sizes(value))
        and any(term in normalized for term in DISPLAY_HINT_TERMS)
    )


def has_motherboard_facet(value: str) -> bool:
    normalized = normalize_match_text(value)
    tokens = set(match_tokens(value))
    return (
        has_any_match_term(normalized, tokens, MOTHERBOARD_QUERY_TERMS)
        or R_MOTHERBOARD_CHIPSET.search(normalized) is not None
        or any(term in normalized for term in MOTHERBOARD_SOCKET_TERMS)
    )


def has_power_supply_facet(value: str) -> bool:
    normalized = normalize_match_text(value)
    tokens = set(match_tokens(value))
    if has_any_match_term(normalized, tokens, POWER_SUPPLY_QUERY_TERMS):
        return True
    if R_POWER_WATTAGE.search(normalized) and any(
        term in normalized for term in POWER_SUPPLY_HINT_TERMS
    ):
        return True
    return False


def has_case_facet(value: str) -> bool:
    normalized = normalize_match_text(value)
    tokens = set(match_tokens(value))
    return has_any_match_term(normalized, tokens, CASE_QUERY_TERMS)


def has_cooler_facet(value: str) -> bool:
    normalized = normalize_match_text(value)
    tokens = set(match_tokens(value))
    return has_any_match_term(normalized, tokens, COOLER_QUERY_TERMS)


def is_monitor_query(query: str) -> bool:
    return has_monitor_facet(query)


def is_memory_query(query: str) -> bool:
    return has_memory_facet(query)


def is_storage_query(query: str) -> bool:
    return has_storage_facet(query)


def is_motherboard_query(query: str) -> bool:
    return has_motherboard_facet(query)


def is_power_supply_query(query: str) -> bool:
    query_match = normalize_match_text(query)
    if any(term in query_match for term in NOTEBOOK_TERMS) and not any(
        marker in query_match for marker in ("80 plus", "80plus", "modular", "psu")
    ):
        return False
    return has_power_supply_facet(query)


def is_case_query(query: str) -> bool:
    return has_case_facet(query)


def is_cooler_query(query: str) -> bool:
    return has_cooler_facet(query)


def query_optional_tokens(query: str, resolved_category: str) -> set[str]:
    ignored: set[str] = set()

    if resolved_category == "monitor":
        ignored.update(match_tokens("monitor display ultrawide"))
        ignored.update(display_size_query_tokens(query))
    elif resolved_category == "memoria":
        ignored.update(match_tokens("memoria memoria ram ram"))
    elif resolved_category == "placa-mae":
        ignored.update(match_tokens("placa mae motherboard mainboard mobo"))
    elif resolved_category == "fonte":
        ignored.update(match_tokens("fonte psu"))
    elif resolved_category == "gabinete":
        ignored.update(match_tokens("gabinete case"))
    elif resolved_category == "cooler":
        ignored.update(match_tokens("cooler"))

    return ignored


def title_matches_category(title: str, resolved_category: str, query: str = "") -> bool:
    if resolved_category == "monitor":
        return has_monitor_facet(title)
    if resolved_category == "memoria":
        return has_memory_facet(title)
    if resolved_category == "armazenamento":
        return has_storage_facet(title)
    if resolved_category == "placa-mae":
        return has_motherboard_facet(title)
    if resolved_category == "fonte":
        return has_power_supply_facet(title)
    if resolved_category == "gabinete":
        return has_case_facet(title)
    if resolved_category == "cooler":
        return has_cooler_facet(title)
    if resolved_category == "notebook":
        normalized = normalize_match_text(title)
        return has_any_match_term(normalized, set(match_tokens(title)), NOTEBOOK_TERMS)
    if resolved_category == "pc-completo":
        normalized = normalize_match_text(title)
        return has_any_match_term(normalized, set(match_tokens(title)), PC_TERMS)
    if resolved_category == "placa-de-video":
        normalized = normalize_match_text(title)
        return has_any_match_term(normalized, set(match_tokens(title)), GPU_QUERY_TERMS)
    if resolved_category == "processador":
        return is_processor_query(title)
    return True


def has_processor_accessory_mismatch(query: str, title: str) -> bool:
    if not is_processor_bundle_query(query):
        return False

    title_match = normalize_match_text(title)
    if not any(term in title_match for term in PROCESSOR_ACCESSORY_TERMS):
        return False

    if any(term in title_match for term in ("placa mae", "motherboard", "processador")):
        return False
    if extract_xeon_signature(title):
        return False
    if has_memory_facet(title) or has_storage_facet(title):
        return False
    return True


def build_xeon_bundle_search_query(query: str) -> str:
    if not is_xeon_bundle_query(query):
        return ""

    query_match = normalize_match_text(query)
    signature = extract_xeon_signature(query)
    parts: list[str] = []

    if any(term in query_match for term in ("kit", "combo")):
        parts.append("kit")

    parts.append("xeon")

    if signature:
        family, model, version = signature
        if family:
            parts.append(family)
        parts.append(model)
        if version:
            parts.append(version)

    for term in XEON_PLATFORM_TERMS:
        if term in query_match:
            parts.append(term)
            break

    return normalize_text(" ".join(parts))


def strip_query_terms(query: str, removable_terms: tuple[str, ...]) -> str:
    normalized = normalize_match_text(query)
    if not normalized:
        return ""

    pattern = re.compile(
        r"\b(?:"
        + "|".join(re.escape(term) for term in removable_terms)
        + r")\b"
    )
    return normalize_text(pattern.sub(" ", normalized))


def strip_memory_size_terms(query: str) -> str:
    normalized = normalize_match_text(query)
    if not normalized:
        return ""
    return normalize_text(R_MEMORY_SIZE.sub(" ", normalized))


def is_display_size_query(query: str) -> bool:
    tokens = set(match_tokens(query))
    return any(term in tokens for term in DISPLAY_QUERY_TERMS) and bool(
        extract_display_sizes(query)
    )


def has_display_size_match(query: str, title: str) -> bool:
    query_sizes = extract_display_sizes(query)
    title_sizes = extract_display_sizes(title)
    if not query_sizes or not title_sizes:
        return False

    for query_size in query_sizes:
        if any(abs(title_size - query_size) <= DISPLAY_SIZE_TOLERANCE for title_size in title_sizes):
            return True
    return False


def build_gpu_core_query(query: str) -> str:
    tokens = [
        token
        for token in match_tokens(strip_memory_size_terms(query))
        if token not in QUERY_NOISE_TOKENS and token != "gb"
    ]
    if not tokens:
        return ""

    core_tokens: list[str] = []

    for token in tokens:
        if token in GPU_FAMILY_TERMS:
            continue
        if token.isdigit():
            core_tokens.append(token)
            continue
        if core_tokens and token in GPU_VARIANT_TERMS:
            core_tokens.append(token)
            continue
        if core_tokens:
            break

    return normalize_text(" ".join(core_tokens))


def build_gpu_compact_query(query: str) -> str:
    tokens = match_tokens(strip_memory_size_terms(query))
    if not tokens:
        return ""

    family = ""
    model = ""
    suffix: list[str] = []

    for token in tokens:
        if not family and token in GPU_FAMILY_TERMS:
            family = token
            continue
        if family and not model and token.isdigit():
            model = token
            continue
        if family and model and token in GPU_VARIANT_TERMS:
            suffix.append(token)
            continue
        if family and model:
            break

    compact = "".join([family, model, *suffix])
    return normalize_text(compact)


def dedupe_terms(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in unique:
            continue
        unique.append(normalized)
    return unique


def build_search_candidates(query: str, category: str = "auto") -> list[str]:
    resolved_category = resolve_category(query, category)
    candidates = [
        normalize_search_query_text(query),
        normalize_text(query),
    ]

    if is_switch_console_query(query):
        candidates.append(strip_query_terms(query, ("nintendo",)))
        candidates.append(
            replace_query_terms(
                query,
                {
                    "desbloqueado": "destravado",
                    "desbloqueada": "destravada",
                },
            )
        )
        candidates.append(
            replace_query_terms(
                query,
                {
                    "desbloqueado": "modificado",
                    "desbloqueada": "modificada",
                },
            )
        )
        candidates.append(strip_query_terms(query, SWITCH_UNLOCK_QUERY_TERMS))

    if resolved_category == "placa-de-video":
        gpu_base_query = strip_query_terms(query, GPU_SEARCH_NOISE_TERMS)
        candidates.append(gpu_base_query)
        candidates.append(build_gpu_compact_query(gpu_base_query))
        candidates.append(strip_memory_size_terms(gpu_base_query))
        candidates.append(build_gpu_core_query(gpu_base_query))

    if resolved_category == "processador":
        candidates.append(strip_query_terms(query, PROCESSOR_SEARCH_NOISE_TERMS))
        if is_xeon_query(query):
            candidates.append(build_xeon_bundle_search_query(query))
            candidates.append(build_xeon_search_query(query))
    elif resolved_category == "memoria":
        candidates.append(strip_query_terms(query, MEMORY_SEARCH_NOISE_TERMS))
    elif resolved_category == "placa-mae":
        candidates.append(strip_query_terms(query, MOTHERBOARD_SEARCH_NOISE_TERMS))
    elif resolved_category == "fonte":
        candidates.append(strip_query_terms(query, POWER_SUPPLY_SEARCH_NOISE_TERMS))
    elif resolved_category == "gabinete":
        candidates.append(strip_query_terms(query, CASE_SEARCH_NOISE_TERMS))
    elif resolved_category == "cooler":
        candidates.append(strip_query_terms(query, COOLER_SEARCH_NOISE_TERMS))

    if is_display_size_query(query):
        candidates.append(strip_query_terms(query, INCH_UNIT_TERMS))

    return dedupe_terms(candidates)[:SEARCH_FALLBACK_MAX_ATTEMPTS]


def determine_search_target_count(
    platform: str,
    max_results: int,
    resolved_category: str,
) -> int:
    if platform in EARLY_SUCCESS_TARGET_PLATFORMS:
        return 1
    base_target = 3 if resolved_category == "processador" else 2
    return min(max_results, base_target)


def has_xeon_bundle_query_match(query: str, title: str) -> bool:
    if not is_xeon_bundle_query(query):
        return False

    query_match = normalize_match_text(query)
    title_match = normalize_match_text(title)
    title_tokens = set(match_tokens(title))

    if "xeon" not in title_match:
        return False

    platform_terms = [term for term in XEON_PLATFORM_TERMS if term in query_match]
    if platform_terms and not any(term in title_match for term in platform_terms):
        return False

    if any(term in query_match for term in ("kit", "combo")) and not any(
        term in title_tokens or term in title_match for term in ("kit", "combo")
    ):
        return False

    query_signature = extract_xeon_signature(query)
    if query_signature and not has_xeon_model_match(query, title):
        return False

    soft_groups = 0
    soft_hits = 0

    if has_memory_facet(query):
        soft_groups += 1
        if has_memory_facet(title):
            soft_hits += 1

    if has_storage_facet(query):
        soft_groups += 1
        if has_storage_facet(title):
            soft_hits += 1

    return soft_groups == 0 or soft_hits >= 1


def looks_like_standalone_gpu_listing(title: str) -> bool:
    title_match = normalize_match_text(title)
    title_tokens = set(match_tokens(title))

    if not has_any_match_term(title_match, title_tokens, GPU_QUERY_TERMS):
        return False

    if any(
        marker in title_match
        for marker in (
            "graphics card",
            "video card",
            "placa de video",
            "gddr",
            "pcie",
            "hdmi",
            "displayport",
            "display port",
            "cuda",
        )
    ):
        return True

    return has_memory_facet(title)


def has_gpu_bundle_mismatch(query: str, title: str) -> bool:
    query_match = normalize_match_text(query)
    title_match = normalize_match_text(title)

    if any(term in title_match and term not in query_match for term in GPU_STRICT_BUNDLE_TERMS):
        return True

    if any(term in title_match and term not in query_match for term in GPU_GENERIC_CONTEXT_TERMS):
        return not looks_like_standalone_gpu_listing(title)

    return False


def has_gpu_accessory_mismatch(query: str, title: str) -> bool:
    title_match = normalize_match_text(title)
    query_match = normalize_match_text(query)
    title_tokens = set(match_tokens(title))
    query_tokens = set(match_tokens(query))

    for term in GPU_ACCESSORY_TERMS:
        if not has_match_term(title_match, title_tokens, term):
            continue
        if has_match_term(query_match, query_tokens, term):
            continue
        if term in {"memoria", "memoria ram"} and any(
            marker in title_match
            for marker in ("memoria de video", "video memory", "gddr")
        ):
            continue
        return True

    return False


def title_contains_query(query: str, title: str, category: str = "auto") -> bool:
    title_match = normalize_match_text(title)
    title_compact = compact_text(title)
    title_tokens = set(match_tokens(title))
    tokens = query_tokens(query)
    xeon_query = is_xeon_query(query)
    query_xeon_signature = extract_xeon_signature(query)
    resolved_category = resolve_category(query, category)

    tokens = [token for token in tokens if token not in query_optional_tokens(query, resolved_category)]

    if not tokens:
        if is_display_size_query(query):
            return has_display_size_match(query, title) and title_matches_category(
                title,
                resolved_category,
                query,
            )
        return title_matches_category(title, resolved_category, query)

    if is_xeon_bundle_query(query):
        return has_xeon_bundle_query_match(query, title)

    if xeon_query and query_xeon_signature:
        return has_xeon_model_match(query, title)

    if is_display_size_query(query):
        if not has_display_size_match(query, title):
            return False
        ignored_tokens = display_size_query_tokens(query)
        tokens = [token for token in tokens if token not in ignored_tokens]

    compact_query = "".join(tokens)
    if compact_query and compact_query in title_compact:
        return True

    return all(token in title_tokens for token in tokens)


def normalize_category_name(category: str | None) -> str:
    normalized_match = normalize_match_text(category or "auto")
    if normalized_match in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[normalized_match]

    normalized_slug = slugify(category or "auto")
    if normalized_slug in CATEGORY_CHOICES:
        return normalized_slug

    return normalized_slug


def has_gpu_variant_mismatch(query: str, title: str) -> bool:
    query_terms = query_tokens(query)
    title_terms = match_tokens(title)

    if not any(term in query_terms for term in ("gtx", "rtx", "rx", "geforce", "radeon")):
        return False

    if any(term in query_terms for term in GPU_VARIANT_TERMS):
        return False

    for index, token in enumerate(title_terms[:-1]):
        if not token.isdigit() or token not in query_terms:
            continue
        variant = title_terms[index + 1]
        if variant in GPU_VARIANT_TERMS and variant not in query_terms:
            return True

    return False


def resolve_category(query: str, category: str | None) -> str:
    normalized_category = normalize_category_name(category)
    if normalized_category in CATEGORY_CHOICES and normalized_category != "auto":
        return normalized_category

    query_match = normalize_match_text(query)
    if any(term in query_match for term in GPU_QUERY_TERMS):
        return "placa-de-video"
    if is_processor_query(query):
        return "processador"
    if is_cooler_query(query):
        return "cooler"
    if is_motherboard_query(query):
        return "placa-mae"
    if is_memory_query(query):
        return "memoria"
    if is_storage_query(query):
        return "armazenamento"
    if is_monitor_query(query):
        return "monitor"
    if is_power_supply_query(query):
        return "fonte"
    if is_case_query(query):
        return "gabinete"
    if any(term in query_match for term in NOTEBOOK_TERMS):
        return "notebook"
    if any(term in query_match for term in PC_TERMS):
        return "pc-completo"
    return "auto"


def has_unrequested_match_terms(
    query_match: str,
    query_token_set: set[str],
    title_match: str,
    title_tokens: set[str],
    terms: tuple[str, ...],
) -> bool:
    return any(
        has_match_term(title_match, title_tokens, term)
        and not has_match_term(query_match, query_token_set, term)
        for term in terms
    )


def evaluate_title_reason(query: str, title: str, resolved_category: str = "auto") -> str:
    title_match = normalize_match_text(title)
    query_match = normalize_match_text(query)
    title_tokens = set(match_tokens(title))
    query_token_set = set(match_tokens(query))
    gpu_query = any(term in query_match for term in GPU_QUERY_TERMS)
    xeon_query = is_xeon_query(query)
    processor_bundle_query = is_processor_bundle_query(query)

    if not title_contains_query(query, title, resolved_category):
        return "query_mismatch"

    if any(term in title_match for term in TITLE_BLOCK_TERMS) or has_untested_terms(title):
        return "blocked_term"

    if xeon_query and has_xeon_bundle_mismatch(query, title):
        return "bundle_term"

    if is_processor_query(query) and has_processor_bundle_mismatch(query, title):
        return "bundle_term"

    if has_server_oem_mismatch(query, title):
        return "bundle_term"

    if (resolved_category == "placa-de-video" or gpu_query) and has_gpu_bundle_mismatch(query, title):
        return "bundle_term"

    component_categories = {"monitor", "memoria", "armazenamento", "placa-mae", "fonte", "gabinete", "cooler"}

    if (
        resolved_category not in {"placa-de-video", *component_categories}
        and not gpu_query
        and any(term in title_match and term not in query_match for term in BUNDLE_TERMS)
    ):
        return "bundle_term"

    if (resolved_category == "placa-de-video" or gpu_query) and has_gpu_variant_mismatch(query, title):
        return "variant_mismatch"

    if resolved_category == "placa-de-video":
        if has_any_match_term(title_match, title_tokens, NOTEBOOK_TERMS):
            return "category_mismatch"
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            PC_TERMS,
        ):
            return "category_mismatch"
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            SYSTEM_SPEC_TERMS,
        ):
            return "category_mismatch"
        if has_gpu_accessory_mismatch(query, title):
            return "category_mismatch"
    elif resolved_category == "notebook":
        if not has_any_match_term(title_match, title_tokens, NOTEBOOK_TERMS):
            return "category_mismatch"
    elif resolved_category == "pc-completo":
        if not has_any_match_term(title_match, title_tokens, PC_TERMS):
            return "category_mismatch"
    elif resolved_category == "processador":
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            NOTEBOOK_TERMS,
        ):
            return "category_mismatch"
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            PC_TERMS,
        ):
            return "category_mismatch"
        if (
            not processor_bundle_query
            and has_unrequested_match_terms(
                query_match,
                query_token_set,
                title_match,
                title_tokens,
                PROCESSOR_BUNDLE_TERMS,
            )
        ):
            return "bundle_term"
    elif resolved_category == "monitor":
        if not title_matches_category(title, resolved_category, query):
            return "category_mismatch"
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            NOTEBOOK_TERMS + PC_TERMS,
        ):
            return "category_mismatch"
    elif resolved_category == "memoria":
        if not title_matches_category(title, resolved_category, query):
            return "category_mismatch"
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            PC_TERMS,
        ):
            return "category_mismatch"
    elif resolved_category == "armazenamento":
        if not title_matches_category(title, resolved_category, query):
            return "category_mismatch"
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            PC_TERMS,
        ):
            return "category_mismatch"
    elif resolved_category == "placa-mae":
        if not title_matches_category(title, resolved_category, query):
            return "category_mismatch"
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            NOTEBOOK_TERMS + PC_TERMS,
        ):
            return "category_mismatch"
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            MOTHERBOARD_BUNDLE_TERMS,
        ):
            return "bundle_term"
    elif resolved_category == "fonte":
        if not title_matches_category(title, resolved_category, query):
            return "category_mismatch"
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            PC_TERMS,
        ):
            return "category_mismatch"
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            POWER_SUPPLY_ACCESSORY_TERMS,
        ):
            return "category_mismatch"
    elif resolved_category == "gabinete":
        if not title_matches_category(title, resolved_category, query):
            return "category_mismatch"
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            NOTEBOOK_TERMS + PC_TERMS,
        ):
            return "category_mismatch"
    elif resolved_category == "cooler":
        if not title_matches_category(title, resolved_category, query):
            return "category_mismatch"
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            PC_TERMS,
        ):
            return "category_mismatch"
    elif gpu_query:
        if has_unrequested_match_terms(
            query_match,
            query_token_set,
            title_match,
            title_tokens,
            SYSTEM_SPEC_TERMS,
        ):
            return "bundle_term"

    return ""


def quartiles(values: list[float]) -> tuple[float, float]:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    lower = ordered[:midpoint]
    upper = ordered[midpoint:] if len(ordered) % 2 == 0 else ordered[midpoint + 1 :]
    return median(lower), median(upper)


def listing_effective_price_value(item: "Listing") -> float | None:
    comparison_value = getattr(item, "comparison_price_value", None)
    try:
        if comparison_value not in (None, ""):
            return float(comparison_value)
    except (TypeError, ValueError):
        pass
    return item.price_value


def build_price_stats_from_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "priced_items": 0,
            "considered_items": 0,
            "discarded_outliers": 0,
            "average_price": None,
            "median_price": None,
            "min_price": None,
            "max_price": None,
            "automatic_min_price": None,
            "automatic_max_price": None,
        }

    med = median(values)

    if len(values) >= 4:
        q1, q3 = quartiles(values)
        iqr = q3 - q1
        iqr_lower = max(0.0, q1 - (1.5 * iqr))
        iqr_upper = q3 + (1.5 * iqr)
        lower = max(iqr_lower, med * 0.55)
        upper = min(max(iqr_upper, med * 1.50), med * 1.80)
        if lower >= upper:
            lower = iqr_lower
            upper = iqr_upper
    else:
        lower = med * 0.55
        upper = med * 1.80

    considered = [value for value in values if lower <= value <= upper]
    if not considered:
        considered = list(values)
        lower = min(values)
        upper = max(values)

    return {
        "priced_items": len(values),
        "considered_items": len(considered),
        "discarded_outliers": len(values) - len(considered),
        "average_price": round(mean(considered), 2),
        "median_price": round(median(considered), 2),
        "min_price": round(min(considered), 2),
        "max_price": round(max(considered), 2),
        "automatic_min_price": round(lower, 2),
        "automatic_max_price": round(upper, 2),
    }


def build_price_stats(items: list["Listing"]) -> dict[str, Any]:
    values: list[float] = []
    for item in items:
        effective_price = listing_effective_price_value(item)
        if effective_price is not None:
            values.append(effective_price)
    return build_price_stats_from_values(values)


def clone_optional_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    return None


def item_price_value(
    item: dict[str, Any],
    comparison: bool = False,
) -> float | None:
    raw_price_value = (
        item.get("comparison_price_value")
        if comparison and item.get("comparison_price_value") not in (None, "")
        else item.get("price_value")
    )
    price_value: float | None
    try:
        price_value = None if raw_price_value in (None, "") else float(raw_price_value)
    except (TypeError, ValueError):
        price_value = None
    return price_value


def item_price_label(
    item: dict[str, Any],
    comparison: bool = False,
) -> str:
    raw_price = (
        item.get("comparison_price")
        if comparison and item.get("comparison_price")
        else item.get("price", "")
    )
    return normalize_text(str(raw_price or ""))


def build_import_tax_comparison_adjustment(
    price_value: float | None,
    shipping_origin_code: str,
    import_tax_value: float | None,
    import_tax_percent: float | None = None,
) -> tuple[float | None, str, dict[str, Any] | None]:
    if price_value in (None, ""):
        return None, "", None

    origin_code = normalize_aliexpress_ship_from(shipping_origin_code)
    if not origin_code or origin_code == "BR":
        return None, "", None

    try:
        tax_value = None if import_tax_value in (None, "") else float(import_tax_value)
    except (TypeError, ValueError):
        tax_value = None

    try:
        tax_percent_value = (
            None if import_tax_percent in (None, "") else float(import_tax_percent)
        )
    except (TypeError, ValueError):
        tax_percent_value = None

    estimated = False
    if tax_value is None or tax_value <= 0:
        fallback_percent = max(0.0, float(SETTINGS.import_tax_fallback_percent or 0.0))
        if fallback_percent <= 0:
            return None, "", None
        tax_percent_value = fallback_percent
        tax_value = round(float(price_value) * (fallback_percent / 100.0), 2)
        estimated = True

    adjusted_price_value = round(float(price_value) + tax_value, 2)
    adjusted_price = format_brl_value(adjusted_price_value)
    base_price = format_brl_value(price_value)
    tax_label = format_brl_value(tax_value)
    percent_label = format_percent_value(tax_percent_value) if tax_percent_value is not None else ""

    if estimated:
        origin_country = aliexpress_ship_from_label(origin_code) or "fora do Brasil"
        summary = (
            f"Comparacao usa {adjusted_price} com estimativa de {percent_label} "
            f"(~{tax_label}) para envio de {origin_country}."
        )
        adjustment = {
            "kind": "import_tax_estimate",
            "label": "Preco + taxa estimada",
            "summary": summary,
            "base_price_value": round(float(price_value), 2),
            "tax_percent": tax_percent_value,
            "tax_value": round(tax_value, 2),
            "adjusted_price_value": adjusted_price_value,
            "display_tax_label": f"Estimativa {percent_label} (~{tax_label})",
        }
    else:
        summary = (
            f"Comparacao usa {adjusted_price} "
            f"({base_price} do produto + {tax_label} de taxa)."
        )
        if percent_label:
            summary = (
                f"Comparacao usa {adjusted_price} "
                f"({base_price} do produto + {tax_label} de taxa, {percent_label})."
            )
        adjustment = {
            "kind": "import_tax",
            "label": "Preco + taxa de importacao",
            "summary": summary,
            "base_price_value": round(float(price_value), 2),
            "tax_percent": tax_percent_value,
            "tax_value": round(tax_value, 2),
            "adjusted_price_value": adjusted_price_value,
            "display_tax_label": (
                f"{percent_label} (~{tax_label})" if percent_label else tax_label
            ),
        }

    return (
        adjusted_price_value,
        adjusted_price,
        adjustment,
    )


def apply_import_tax_comparison_adjustment(item: "Listing") -> "Listing":
    adjusted_price_value, adjusted_price, adjustment = build_import_tax_comparison_adjustment(
        price_value=item.price_value,
        shipping_origin_code=item.shipping_origin_code,
        import_tax_value=item.import_tax_value,
        import_tax_percent=item.import_tax_percent,
    )
    item.comparison_price_value = adjusted_price_value
    item.comparison_price = adjusted_price
    item.comparison_adjustment = adjustment
    if adjustment and adjustment.get("kind") == "import_tax_estimate":
        item.import_tax_percent = parse_optional_float(adjustment.get("tax_percent"))
        item.import_tax_value = parse_optional_float(adjustment.get("tax_value"))
        if is_missing_import_tax_label(item.import_tax_label):
            item.import_tax_label = normalize_text(str(adjustment.get("display_tax_label", "")))
    return item


def listing_from_payload(item: dict[str, Any], comparison: bool = False) -> "Listing":
    price_value = item_price_value(item, comparison=comparison)

    return Listing(
        source=normalize_text(str(item.get("source", ""))),
        title=normalize_text(str(item.get("title", ""))),
        price=item_price_label(item, comparison=comparison),
        price_value=price_value,
        rating=normalize_rating_value(item.get("rating")),
        sold_count=parse_optional_int(item.get("sold_count")),
        sold_label=normalize_text(str(item.get("sold_label", ""))),
        url=str(item.get("url", "") or ""),
        location=normalize_text(str(item.get("location", ""))),
        posted_at=normalize_text(str(item.get("posted_at", ""))),
        installment=normalize_text(str(item.get("installment", ""))),
        shipping=normalize_text(str(item.get("shipping", ""))),
        shipping_origin=normalize_text(str(item.get("shipping_origin", ""))),
        shipping_origin_code=normalize_text(str(item.get("shipping_origin_code", ""))).upper(),
        is_imported=(
            bool(item.get("is_imported"))
            if item.get("is_imported") is not None
            else None
        ),
        import_tax_percent=parse_optional_float(item.get("import_tax_percent")),
        import_tax_value=parse_optional_float(item.get("import_tax_value")),
        import_tax_label=normalize_text(str(item.get("import_tax_label", ""))),
        comparison_price=normalize_text(str(item.get("comparison_price", ""))),
        comparison_price_value=parse_optional_float(item.get("comparison_price_value")),
        comparison_adjustment=clone_optional_mapping(item.get("comparison_adjustment")),
        image=str(item.get("image", "") or ""),
        raw_text=normalize_text(str(item.get("raw_text", ""))),
    )


def build_deal_insight(
    item: dict[str, Any],
    reference_price: float | None,
    lower_bound: float | None,
    upper_bound: float | None,
    comparison_price_value: float | None = None,
) -> dict[str, Any] | None:
    price_value = comparison_price_value
    if price_value is None:
        price_value = item_price_value(item, comparison=True)
    if price_value is None or not reference_price:
        return None

    delta_value = round(reference_price - price_value, 2)
    delta_percent = round((delta_value / reference_price) * 100, 1)
    below_range = lower_bound is not None and price_value < lower_bound
    above_range = upper_bound is not None and price_value > upper_bound

    if below_range and delta_percent >= 12:
        label = "Fora da curva"
        tone = "watch"
        summary = (
            f"{abs(delta_percent):.1f}% abaixo da mediana e abaixo da faixa automatica. "
            "Vale checar estado e reputacao."
        )
    elif delta_percent >= 18:
        label = "Oportunidade forte"
        tone = "hot"
        summary = f"{delta_percent:.1f}% abaixo da mediana filtrada."
    elif delta_percent >= 8:
        label = "Boa oportunidade"
        tone = "good"
        summary = f"{delta_percent:.1f}% abaixo da mediana filtrada."
    elif delta_percent > -8:
        label = "Na faixa"
        tone = "fair"
        if delta_percent >= 0:
            summary = f"{delta_percent:.1f}% abaixo da mediana, dentro da faixa normal."
        else:
            summary = f"{abs(delta_percent):.1f}% acima da mediana, mas ainda dentro da faixa normal."
    else:
        label = "Acima do mercado"
        tone = "high"
        summary = f"{abs(delta_percent):.1f}% acima da mediana filtrada."

    score = round(delta_percent * 3)
    if below_range:
        score -= 12
    if above_range:
        score -= 20

    return {
        "label": label,
        "tone": tone,
        "score": max(-100, min(100, score)),
        "reference_price": round(reference_price, 2),
        "delta_value": delta_value,
        "delta_percent": delta_percent,
        "below_range": below_range,
        "above_range": above_range,
        "summary": summary,
    }


def summarize_market_item(item: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "source": item.get("source", ""),
        "title": item.get("title", ""),
        "price": item_price_label(item, comparison=True),
        "price_value": item_price_value(item, comparison=True),
        "original_price": normalize_text(str(item.get("price", ""))),
        "original_price_value": item_price_value(item, comparison=False),
        "comparison_price": normalize_text(str(item.get("comparison_price", ""))),
        "comparison_price_value": parse_optional_float(item.get("comparison_price_value")),
        "rating": normalize_rating_value(item.get("rating")),
        "sold_count": parse_optional_int(item.get("sold_count")),
        "sold_label": normalize_text(str(item.get("sold_label", ""))),
        "url": item.get("url", ""),
        "location": item.get("location", ""),
        "posted_at": item.get("posted_at", ""),
        "shipping_origin": normalize_text(str(item.get("shipping_origin", ""))),
        "shipping_origin_code": normalize_text(str(item.get("shipping_origin_code", ""))).upper(),
        "is_imported": item.get("is_imported"),
        "import_tax_percent": parse_optional_float(item.get("import_tax_percent")),
        "import_tax_value": parse_optional_float(item.get("import_tax_value")),
        "import_tax_label": normalize_text(str(item.get("import_tax_label", ""))),
        "deal": clone_optional_mapping(item.get("deal")),
        "comparison_adjustment": clone_optional_mapping(item.get("comparison_adjustment")),
    }
    return summary


def flatten_market_items(results: dict[str, Any]) -> list[dict[str, Any]]:
    flat_items: list[dict[str, Any]] = []
    for platform, result in results.items():
        for raw_item in result.get("items") or []:
            if not isinstance(raw_item, dict):
                continue
            raw_item["source"] = normalize_text(str(raw_item.get("source") or platform))
            flat_items.append(raw_item)
    return flat_items


def build_market_insights(results: dict[str, Any]) -> dict[str, Any]:
    flat_items = flatten_market_items(results)

    if not flat_items:
        return {
            "priced_items": 0,
            "opportunity_count": 0,
            "above_market_count": 0,
            "reference_price": None,
            "average_price": None,
            "median_price": None,
            "automatic_min_price": None,
            "automatic_max_price": None,
            "cheapest_item": None,
            "best_opportunity": None,
            "top_opportunities": [],
            "summary_note": "Sem itens suficientes para montar um radar de oportunidades.",
        }

    prepared_items: list[tuple[dict[str, Any], float | None]] = []
    comparison_values: list[float] = []
    has_import_tax_adjustment = False
    has_import_tax_estimate = False
    for item in flat_items:
        price_value = item_price_value(item, comparison=True)
        prepared_items.append((item, price_value))
        if price_value is not None:
            comparison_values.append(price_value)

        adjustment = item.get("comparison_adjustment")
        if isinstance(adjustment, dict):
            kind = adjustment.get("kind")
            if kind in {"import_tax", "import_tax_estimate"}:
                has_import_tax_adjustment = True
            if kind == "import_tax_estimate":
                has_import_tax_estimate = True

    stats = build_price_stats_from_values(comparison_values)
    reference_price = stats.get("median_price") or stats.get("average_price")
    lower_bound = stats.get("automatic_min_price")
    upper_bound = stats.get("automatic_max_price")

    priced_items: list[tuple[dict[str, Any], float]] = []
    for item, price_value in prepared_items:
        deal = build_deal_insight(
            item,
            reference_price,
            lower_bound,
            upper_bound,
            comparison_price_value=price_value,
        )
        if not deal:
            item.pop("deal", None)
            continue
        item["deal"] = deal
        if price_value is not None:
            priced_items.append((item, price_value))

    top_opportunities = [
        (item, price_value)
        for item, price_value in priced_items
        if item.get("deal", {}).get("tone") in {"hot", "good", "watch"}
    ]
    top_opportunities.sort(
        key=lambda entry: (
            entry[0].get("deal", {}).get("score", -999),
            entry[0].get("deal", {}).get("delta_value", 0.0),
            -entry[1],
        ),
        reverse=True,
    )

    cheapest_entry = min(
        priced_items,
        key=lambda entry: entry[1],
        default=None,
    )
    cheapest_item = cheapest_entry[0] if cheapest_entry else None
    best_opportunity = top_opportunities[0][0] if top_opportunities else None
    summary_note = "Indicadores baseados na mediana filtrada da busca atual."
    if has_import_tax_adjustment:
        summary_note = (
            f"{summary_note} Itens enviados de fora do Brasil entram "
            "na comparacao pelo custo final, nao so pelo preco do anuncio."
        )
        if has_import_tax_estimate:
            summary_note = (
                f"{summary_note} Quando o AliExpress nao informa a taxa, o sistema "
                f"estima {format_percent_value(SETTINGS.import_tax_fallback_percent)} "
                "para nao deixar importados parecerem artificialmente mais baratos."
            )

    return {
        "priced_items": stats.get("priced_items", 0),
        "opportunity_count": sum(
            1
            for item, _price_value in priced_items
            if item.get("deal", {}).get("tone") in {"hot", "good", "watch"}
        ),
        "above_market_count": sum(
            1
            for item, _price_value in priced_items
            if item.get("deal", {}).get("tone") == "high"
        ),
        "reference_price": reference_price,
        "average_price": stats.get("average_price"),
        "median_price": stats.get("median_price"),
        "automatic_min_price": lower_bound,
        "automatic_max_price": upper_bound,
        "cheapest_item": summarize_market_item(cheapest_item) if cheapest_item else None,
        "best_opportunity": summarize_market_item(best_opportunity) if best_opportunity else None,
        "top_opportunities": [summarize_market_item(item) for item, _price_value in top_opportunities[:6]],
        "summary_note": summary_note,
    }


def extract_image(node: Any) -> str:
    image = node.select_one("img")
    if not image:
        return ""
    for attr in ("src", "data-src", "data-lazy", "data-srcset"):
        value = image.get(attr)
        if value:
            return value
    return ""


@dataclass(slots=True)
class Listing:
    source: str
    title: str
    price: str = ""
    price_value: float | None = None
    rating: float | None = None
    sold_count: int | None = None
    sold_label: str = ""
    url: str = ""
    location: str = ""
    posted_at: str = ""
    installment: str = ""
    shipping: str = ""
    shipping_origin: str = ""
    shipping_origin_code: str = ""
    is_imported: bool | None = None
    import_tax_percent: float | None = None
    import_tax_value: float | None = None
    import_tax_label: str = ""
    comparison_price: str = ""
    comparison_price_value: float | None = None
    comparison_adjustment: dict[str, Any] | None = None
    image: str = ""
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "price": self.price,
            "price_value": self.price_value,
            "rating": self.rating,
            "sold_count": self.sold_count,
            "sold_label": self.sold_label,
            "url": self.url,
            "location": self.location,
            "posted_at": self.posted_at,
            "installment": self.installment,
            "shipping": self.shipping,
            "shipping_origin": self.shipping_origin,
            "shipping_origin_code": self.shipping_origin_code,
            "is_imported": self.is_imported,
            "import_tax_percent": self.import_tax_percent,
            "import_tax_value": self.import_tax_value,
            "import_tax_label": self.import_tax_label,
            "comparison_price": self.comparison_price,
            "comparison_price_value": self.comparison_price_value,
            "comparison_adjustment": clone_optional_mapping(self.comparison_adjustment),
            "image": self.image,
            "raw_text": self.raw_text,
        }


def matches_soft_console_query(query: str, item: "Listing") -> bool:
    combined = normalize_text(" ".join(part for part in (item.title, item.raw_text) if part))
    combined_match = normalize_match_text(combined)
    combined_tokens = set(match_tokens(combined))
    compact_combined = compact_text(combined)
    query_term_list = query_tokens(query)
    query_term_set = set(query_term_list)

    if not query_term_list:
        return False

    def has_token(token: str) -> bool:
        return (
            token in combined_tokens
            or token in combined_match
            or token in compact_combined
        )

    if "switch" not in query_term_set:
        return False
    if not has_token("switch"):
        return False

    requires_unlock_marker = any(token in query_term_set for token in SWITCH_POSITIVE_UNLOCK_TERMS)
    has_unlock_marker = any(has_token(marker) for marker in SWITCH_POSITIVE_UNLOCK_TERMS)
    has_service_marker = any(term in combined_match for term in SWITCH_SERVICE_TERMS)
    if has_service_marker and (item.price_value or 0.0) < 900:
        return False
    if has_switch_unlock_negation(item):
        return False
    if requires_unlock_marker and not has_unlock_marker:
        return False

    console_markers = (
        "bloqueado",
        "console",
        "desbloqueado",
        "hac",
        "lite",
        "oled",
        "v1",
        "v2",
        "videogame",
    )
    has_console_marker = any(has_token(marker) for marker in console_markers)
    has_accessory_marker = any(term in combined_match for term in FACEBOOK_CONSOLE_ACCESSORY_TERMS)
    if has_accessory_marker and not has_console_marker and (item.price_value or 0.0) < 700:
        return False

    strict_terms = [
        token
        for token in query_term_list
        if token not in FACEBOOK_OPTIONAL_QUERY_TOKENS
        and token not in SWITCH_UNLOCK_QUERY_TERMS
        and token != "nintendo"
    ]
    if not strict_terms:
        strict_terms = ["switch"]

    return all(has_token(token) for token in strict_terms)


def looks_like_switch_service_listing(query: str, item: "Listing") -> bool:
    if not is_switch_console_query(query):
        return False

    combined = normalize_match_text(" ".join(part for part in (item.title, item.raw_text) if part))
    if not any(term in combined for term in SWITCH_SERVICE_TERMS):
        return False

    return (item.price_value or 0.0) < 900


def has_switch_unlock_negation(item: "Listing") -> bool:
    combined = normalize_match_text(" ".join(part for part in (item.title, item.raw_text) if part))
    negative_markers = (
        "nao e desbloqueado",
        "nao desbloqueado",
        "nao e destravado",
        "nao destravado",
        "nao e modificado",
        "nao modificado",
        "sem desbloqueio",
        "sem destrava",
        "sem destravar",
    )
    return any(marker in combined for marker in negative_markers)


@dataclass(slots=True)
class BrowserSession:
    driver: webdriver.Chrome
    lock: threading.Lock


@dataclass(slots=True)
class CacheEntry:
    created_at: float
    payload: dict[str, Any]


class ArtifactStore:
    def __init__(self) -> None:
        ARTIFACTS_HTML_DIR.mkdir(parents=True, exist_ok=True)
        ARTIFACTS_JSON_DIR.mkdir(parents=True, exist_ok=True)

    def _filename(self, platform: str, query: str, extension: str) -> Path:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        return Path(f"{stamp}_{platform}_{slugify(query)}.{extension}")

    def save_html(self, platform: str, query: str, html: str, force: bool = False) -> str:
        if not force and not SETTINGS.save_success_html_snapshots:
            return ""
        path = ARTIFACTS_HTML_DIR / self._filename(platform, query, "html")
        path.write_text(html, encoding="utf-8")
        return f"/artifacts/html/{path.name}"

    def save_json(
        self,
        platform: str,
        query: str,
        payload: dict[str, Any],
        force: bool = False,
    ) -> str:
        if not force and not SETTINGS.save_success_json_snapshots:
            return ""
        path = ARTIFACTS_JSON_DIR / self._filename(platform, query, "json")
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return f"/artifacts/json/{path.name}"


def clone_search_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cloned = dict(payload)

    items = cloned.get("items")
    if isinstance(items, list):
        cloned["items"] = [
            (
                {
                    **item,
                    "deal": clone_optional_mapping(item.get("deal")),
                    "comparison_adjustment": clone_optional_mapping(
                        item.get("comparison_adjustment")
                    ),
                }
                if isinstance(item, dict)
                else item
            )
            for item in items
        ]

    stats = cloned.get("stats")
    if isinstance(stats, dict):
        stats_clone = dict(stats)
        discarded = stats_clone.get("discarded_reasons")
        if isinstance(discarded, dict):
            stats_clone["discarded_reasons"] = dict(discarded)
        cloned["stats"] = stats_clone

    search_attempts = cloned.get("search_attempts")
    if isinstance(search_attempts, list):
        cloned["search_attempts"] = [
            dict(attempt) if isinstance(attempt, dict) else attempt
            for attempt in search_attempts
        ]

    search_terms_used = cloned.get("search_terms_used")
    if isinstance(search_terms_used, list):
        cloned["search_terms_used"] = list(search_terms_used)

    return cloned


def make_soup(
    page_html: str,
    parse_only: SoupStrainer | None = None,
) -> BeautifulSoup:
    if parse_only is None:
        return BeautifulSoup(page_html, "html.parser")
    return BeautifulSoup(page_html, "html.parser", parse_only=parse_only)


class SearchCache:
    def __init__(
        self,
        ttl_seconds: int = SEARCH_CACHE_TTL_SECONDS,
        max_entries: int = SEARCH_CACHE_MAX_ENTRIES,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[tuple[str, str, str, int, bool], CacheEntry] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        expired = [
            key
            for key, entry in self._entries.items()
            if now - entry.created_at > self.ttl_seconds
        ]
        for key in expired:
            self._entries.pop(key, None)

        if len(self._entries) <= self.max_entries:
            return

        ordered = sorted(self._entries.items(), key=lambda item: item[1].created_at)
        overflow = len(self._entries) - self.max_entries
        for key, _entry in ordered[:overflow]:
            self._entries.pop(key, None)

    def get(self, key: tuple[str, str, str, int, bool]) -> dict[str, Any] | None:
        now = time.time()
        with self._lock:
            self._purge(now)
            entry = self._entries.get(key)
            if entry is None:
                return None
            payload = clone_search_payload(entry.payload)

        payload["cache_hit"] = True
        payload["cached_age_seconds"] = round(now - entry.created_at, 1)
        payload["elapsed_ms"] = 0.0
        return payload

    def set(self, key: tuple[str, str, str, int, bool], payload: dict[str, Any]) -> None:
        stored = clone_search_payload(payload)
        stored["cache_hit"] = False
        stored["cached_age_seconds"] = 0.0
        now = time.time()

        with self._lock:
            self._entries[key] = CacheEntry(created_at=now, payload=stored)
            self._purge(now)


class ChromeFactory:
    def __init__(self) -> None:
        PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[tuple[str, bool], BrowserSession] = {}
        self._sessions_guard = threading.Lock()
        self._startup_guard = threading.Lock()
        self._binary_candidates = tuple(self._discover_binaries())
        self._preferred_launch: tuple[Path | None, bool] | None = None

    def _profile_dir(self, profile_name: str) -> Path:
        return PROFILE_ROOT / profile_name

    def _discover_binaries(self) -> list[Path | None]:
        env_candidates = []
        for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env_name)
            if not base:
                continue
            env_candidates.append(Path(base) / "Google/Chrome/Application/chrome.exe")

        candidates = [
            LOCAL_CHROME if LOCAL_CHROME.exists() else None,
            *env_candidates,
            None,
        ]
        binaries: list[Path | None] = []
        for candidate in candidates:
            if candidate is None:
                if None not in binaries:
                    binaries.append(None)
                continue
            if candidate.exists() and candidate not in binaries:
                binaries.append(candidate)
        return binaries

    def _preferred_binaries(self) -> tuple[Path | None, ...]:
        return self._binary_candidates

    def _build_driver_attempts(self) -> list[tuple[Path | None, bool]]:
        attempts: list[tuple[Path | None, bool]] = []

        if self._preferred_launch is not None:
            attempts.append(self._preferred_launch)

        for binary in self._preferred_binaries():
            for safe_mode in (False, True):
                attempt = (binary, safe_mode)
                if attempt not in attempts:
                    attempts.append(attempt)

        return attempts

    def _build_options(
        self,
        profile_name: str,
        headless: bool = False,
        chrome_binary: Path | None = None,
        safe_mode: bool = False,
        persistent_profile: bool = True,
    ) -> Options:
        options = Options()
        options.page_load_strategy = "eager"

        if chrome_binary is not None:
            options.binary_location = str(chrome_binary)

        args = [
            "--lang=pt-BR",
            "--window-size=1440,1100",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-notifications",
            "--remote-debugging-port=0",
            "--no-first-run",
            "--no-default-browser-check",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        ]

        if persistent_profile:
            profile_dir = PROFILE_ROOT / profile_name
            profile_dir.mkdir(parents=True, exist_ok=True)
            args.append(f"--user-data-dir={profile_dir}")

        if headless:
            args.append("--headless=new")
            args.append("--disable-gpu")

        if safe_mode:
            args.extend(
                [
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--disable-extensions",
                ]
            )

        for arg in args:
            options.add_argument(arg)

        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        return options

    def _configure_driver(self, driver: webdriver.Chrome) -> webdriver.Chrome:
        driver.set_page_load_timeout(90)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US', 'en']});
                Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                """,
            },
        )
        return driver

    def _is_startup_crash(self, exc: Exception) -> bool:
        message = normalize_match_text(str(exc))
        return (
            "session not created" in message
            or "chrome failed to start" in message
            or "devtoolsactiveport file doesnt exist" in message
            or "chrome crashed" in message
        )

    def _profile_processes(self, profile_name: str) -> list[tuple[int, int]]:
        if os.name != "nt":
            return []

        profile_dir = str(self._profile_dir(profile_name).resolve()).replace("'", "''")
        command = (
            "$items = Get-CimInstance Win32_Process | "
            f"Where-Object {{ $_.Name -eq 'chrome.exe' -and $_.CommandLine -like '*{profile_dir}*' }} | "
            "Select-Object ProcessId, ParentProcessId; "
            "if ($items) { $items | ConvertTo-Json -Compress }"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []

        raw = (result.stdout or "").strip()
        if not raw:
            return []

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []

        entries = parsed if isinstance(parsed, list) else [parsed]
        processes: list[tuple[int, int]] = []

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pid = int(entry.get("ProcessId") or 0)
            parent_pid = int(entry.get("ParentProcessId") or 0)
            if pid:
                processes.append((pid, parent_pid))

        return processes

    def _cleanup_persistent_profile(self, profile_name: str) -> None:
        profile_dir = self._profile_dir(profile_name)
        parent_ids: set[int] = set()
        chrome_ids: set[int] = set()

        for pid, parent_pid in self._profile_processes(profile_name):
            chrome_ids.add(pid)
            if parent_pid:
                parent_ids.add(parent_pid)

        for pid in sorted(parent_ids):
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                continue

        time.sleep(0.2)

        for pid in sorted(chrome_ids):
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                continue

        time.sleep(0.2)

        for filename in PROFILE_LOCK_FILES:
            try:
                (profile_dir / filename).unlink()
            except FileNotFoundError:
                continue
            except OSError:
                continue

    def _build_driver(
        self,
        profile_name: str,
        headless: bool = False,
        persistent_profile: bool = True,
    ) -> webdriver.Chrome:
        last_error: Exception | None = None
        cleaned_profile = False

        for chrome_binary, safe_mode in self._build_driver_attempts():
            try:
                options = self._build_options(
                    profile_name=profile_name,
                    headless=headless,
                    chrome_binary=chrome_binary,
                    safe_mode=safe_mode,
                    persistent_profile=persistent_profile,
                )
                with self._startup_guard:
                    driver = webdriver.Chrome(options=options)
                self._preferred_launch = (chrome_binary, safe_mode)
                return self._configure_driver(driver)
            except (SessionNotCreatedException, WebDriverException) as exc:
                last_error = exc
                if not self._is_startup_crash(exc):
                    raise
                if persistent_profile and not cleaned_profile:
                    self._cleanup_persistent_profile(profile_name)
                    cleaned_profile = True
                time.sleep(0.35)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Falha inesperada ao iniciar o Chrome.")

    def create(
        self,
        profile_name: str,
        headless: bool = False,
        persistent_profile: bool = True,
    ) -> webdriver.Chrome:
        return self._build_driver(
            profile_name,
            headless=headless,
            persistent_profile=persistent_profile,
        )

    def _is_alive(self, driver: webdriver.Chrome) -> bool:
        try:
            _ = driver.current_url
            return True
        except WebDriverException:
            return False

    def acquire(
        self,
        profile_name: str,
        headless: bool = False,
        persistent_profile: bool = True,
    ) -> webdriver.Chrome:
        if not headless:
            return self._build_driver(
                profile_name,
                headless=False,
                persistent_profile=persistent_profile,
            )

        key = (profile_name, headless)

        while True:
            with self._sessions_guard:
                session = self._sessions.get(key)
                if session is None:
                    session = BrowserSession(
                        driver=self._build_driver(
                            profile_name,
                            headless=headless,
                            persistent_profile=persistent_profile,
                        ),
                        lock=threading.Lock(),
                    )
                    self._sessions[key] = session

            session.lock.acquire()
            if self._is_alive(session.driver):
                return session.driver

            session.lock.release()
            with self._sessions_guard:
                if self._sessions.get(key) is session:
                    self._sessions.pop(key, None)
            try:
                session.driver.quit()
            except Exception:
                pass

    def release(self, profile_name: str, headless: bool = False) -> None:
        if not headless:
            return

        key = (profile_name, headless)
        with self._sessions_guard:
            session = self._sessions.get(key)
        if session is not None and session.lock.locked():
            session.lock.release()


class BaseMarketplaceScraper:
    source = "base"
    profile_name = "default"
    persistent_profile = False
    page_load_timeout_seconds = 90.0
    open_wait_seconds = 2.5
    min_wait_seconds = 0.5
    poll_wait_seconds = 0.2
    post_scroll_wait_seconds = 0.35

    def __init__(self, browser: ChromeFactory, artifacts: ArtifactStore) -> None:
        self.browser = browser
        self.artifacts = artifacts

    def build_search_url(self, query: str) -> str:
        raise NotImplementedError

    def detect_error(self, page_title: str, page_html: str, current_url: str) -> str:
        raise NotImplementedError

    def parse_items(self, page_html: str, max_results: int) -> list[Listing]:
        raise NotImplementedError

    def empty_results_note(self, page_html: str) -> str:
        return ""

    def is_page_ready(self, page_html: str, current_url: str) -> bool:
        return True

    def sort_filtered_items(self, query: str, items: list[Listing]) -> list[Listing]:
        return sort_items_for_query(query, items)

    def post_process_items(
        self,
        items: list[Listing],
        headless: bool,
    ) -> list[Listing]:
        return items

    def should_allow_soft_query_match(
        self,
        query: str,
        item: Listing,
        resolved_category: str,
    ) -> bool:
        return False

    def post_filter_reason(
        self,
        query: str,
        item: Listing,
        resolved_category: str,
    ) -> str:
        return ""

    def filter_items(
        self,
        query: str,
        items: list[Listing],
        max_results: int | None = None,
        category: str = "auto",
    ) -> tuple[list[Listing], dict[str, Any]]:
        resolved_category = resolve_category(query, category)
        approved: list[Listing] = []
        discarded = {
            "query_mismatch": 0,
            "blocked_term": 0,
            "bundle_term": 0,
            "category_mismatch": 0,
            "variant_mismatch": 0,
        }

        for item in items:
            reason = evaluate_title_reason(query, item.title, resolved_category)
            if reason == "query_mismatch" and self.should_allow_soft_query_match(
                query,
                item,
                resolved_category,
            ):
                reason = ""
            if not reason:
                reason = self.post_filter_reason(query, item, resolved_category)
            if reason:
                discarded[reason] += 1
                continue
            approved.append(item)

        approved = self.sort_filtered_items(query, approved)
        stats = build_price_stats(approved)
        stats["resolved_category"] = resolved_category
        stats["scanned_items"] = len(items)
        stats["matched_items"] = len(approved)
        stats["discarded_titles"] = sum(discarded.values())
        stats["discarded_reasons"] = discarded

        if max_results is None:
            return approved, stats
        return approved[:max_results], stats

    def _load_page(self, driver: webdriver.Chrome) -> None:
        started = time.time()
        last_html = ""
        current_url = ""

        while time.time() - started < self.open_wait_seconds:
            elapsed = time.time() - started
            if elapsed < self.min_wait_seconds:
                time.sleep(self.poll_wait_seconds)
                continue

            current_url = driver.current_url
            last_html = driver.page_source
            if self.is_page_ready(last_html, current_url):
                break
            time.sleep(self.poll_wait_seconds)

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.35);")
        time.sleep(self.post_scroll_wait_seconds)

    def after_load(
        self,
        driver: webdriver.Chrome,
        search_url: str,
        headless: bool,
        page_title: str,
        page_html: str,
        current_url: str,
    ) -> tuple[str, str, str]:
        return page_title, page_html, current_url

    def format_driver_error(self, exc: WebDriverException) -> str:
        message = normalize_match_text(summarize_webdriver_message(exc))
        if (
            "session not created" in message
            or "chrome failed to start" in message
            or "devtoolsactiveport file doesnt exist" in message
        ):
            return (
                "O Chrome nao conseguiu iniciar para esta busca. O scraper tentou "
                "reabrir com modo de compatibilidade e fallback do navegador do sistema, "
                "mas a sessao continuou falhando."
            )
        return summarize_webdriver_message(exc) or normalize_text(str(exc))

    def _release_driver(self, driver: webdriver.Chrome, headless: bool) -> None:
        if headless:
            self.browser.release(self.profile_name, headless=True)
            return

        try:
            driver.quit()
        except Exception:
            pass

    def search(
        self,
        query: str,
        max_results: int = 10,
        headless: bool = False,
        category: str = "auto",
        match_query: str | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        display_query = match_query or query
        search_url = self.build_search_url(query)
        driver: webdriver.Chrome | None = None
        page_html = ""
        page_title = ""
        current_url = search_url
        acquired_headless = headless

        try:
            driver = self.browser.acquire(
                self.profile_name,
                headless=headless,
                persistent_profile=self.persistent_profile,
            )
            driver.set_page_load_timeout(self.page_load_timeout_seconds)
            driver.get(search_url)
            self._load_page(driver)

            page_html = driver.page_source
            page_title = driver.title or ""
            current_url = driver.current_url
            page_title, page_html, current_url = self.after_load(
                driver=driver,
                search_url=search_url,
                headless=headless,
                page_title=page_title,
                page_html=page_html,
                current_url=current_url,
            )
            self._release_driver(driver, acquired_headless)
            driver = None
            error = self.detect_error(page_title, page_html, current_url)

            if error:
                html_snapshot = self.artifacts.save_html(
                    self.source,
                    query,
                    page_html,
                    force=True,
                )
                payload = {
                    "source": self.source,
                    "success": False,
                    "query": display_query,
                    "search_term": query,
                    "category": resolve_category(display_query, category),
                    "search_url": search_url,
                    "final_url": current_url,
                    "page_title": page_title,
                    "count": 0,
                    "items": [],
                    "error": error,
                    "note": "",
                    "html_snapshot": html_snapshot,
                }
                payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
                payload["cache_hit"] = False
                payload["cached_age_seconds"] = 0.0
                payload["json_snapshot"] = self.artifacts.save_json(
                    self.source,
                    query,
                    payload,
                    force=True,
                )
                return payload

            raw_limit = max(30, max_results * 4)
            raw_items = self.parse_items(page_html, raw_limit)
            items, stats = self.filter_items(display_query, raw_items, None, category)
            rerank_window = min(
                len(items),
                max(max_results, min(max_results + 8, 20)),
            )
            items = items[:rerank_window]
            items = self.post_process_items(items, headless=headless)
            items = self.sort_filtered_items(display_query, items)
            items = items[:max_results]
            refreshed_stats = build_price_stats(items)
            for field in (
                "priced_items",
                "considered_items",
                "discarded_outliers",
                "average_price",
                "median_price",
                "min_price",
                "max_price",
                "automatic_min_price",
                "automatic_max_price",
            ):
                stats[field] = refreshed_stats[field]
            note_parts = []
            all_titles_missed_query = (
                not items
                and stats["scanned_items"] > 0
                and stats["discarded_reasons"]["query_mismatch"] == stats["scanned_items"]
            )

            if stats["discarded_reasons"]["query_mismatch"]:
                note_parts.append(
                    f"{stats['discarded_reasons']['query_mismatch']} descartados por nao conterem todos os termos da busca no titulo"
                )
            if stats["discarded_reasons"]["category_mismatch"]:
                note_parts.append(
                    f"{stats['discarded_reasons']['category_mismatch']} descartados por nao baterem com o perfil detectado pela busca"
                )
            if stats["discarded_reasons"]["variant_mismatch"]:
                note_parts.append(
                    f"{stats['discarded_reasons']['variant_mismatch']} descartados por serem outra variacao do modelo buscado"
                )
            if stats["discarded_reasons"]["bundle_term"]:
                note_parts.append(
                    f"{stats['discarded_reasons']['bundle_term']} descartados por parecerem bundle, kit ou PC completo"
                )
            if stats["discarded_reasons"]["blocked_term"]:
                note_parts.append(
                    f"{stats['discarded_reasons']['blocked_term']} descartados por termos bloqueados como defeito"
                )
            if stats["discarded_outliers"]:
                note_parts.append(
                    f"{stats['discarded_outliers']} preco(s) ficaram fora do limite automatico e nao entram na media"
                )
            if all_titles_missed_query:
                note_parts.append(
                    "A loja exibiu apenas itens relacionados; nenhum titulo bateu exatamente com o modelo pedido nesta busca."
                )

            payload = {
                "source": self.source,
                "success": True,
                "query": display_query,
                "search_term": query,
                "category": stats["resolved_category"],
                "search_url": search_url,
                "final_url": current_url,
                "page_title": page_title,
                "count": len(items),
                "matched_count": stats["matched_items"],
                "scanned_count": stats["scanned_items"],
                "items": [item.to_dict() for item in items],
                "error": "",
                "note": "; ".join(note_parts)
                if note_parts
                else (
                    ""
                    if items
                    else (
                        self.empty_results_note(page_html)
                        or "Nenhum item aprovado pelos filtros."
                    )
                ),
                "stats": stats,
                "html_snapshot": self.artifacts.save_html(self.source, query, page_html),
            }
            payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
            payload["cache_hit"] = False
            payload["cached_age_seconds"] = 0.0
            payload["json_snapshot"] = self.artifacts.save_json(self.source, query, payload)
            return payload
        except WebDriverException as exc:
            payload = {
                "source": self.source,
                "success": False,
                "query": display_query,
                "search_term": query,
                "category": resolve_category(display_query, category),
                "search_url": search_url,
                "final_url": current_url,
                "page_title": page_title,
                "count": 0,
                "items": [],
                "error": self.format_driver_error(exc),
                "note": "",
                "html_snapshot": "",
            }
            payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
            payload["cache_hit"] = False
            payload["cached_age_seconds"] = 0.0
            payload["json_snapshot"] = self.artifacts.save_json(
                self.source,
                query,
                payload,
                force=True,
            )
            return payload
        except Exception as exc:
            payload = {
                "source": self.source,
                "success": False,
                "query": display_query,
                "search_term": query,
                "category": resolve_category(display_query, category),
                "search_url": search_url,
                "final_url": current_url,
                "page_title": page_title,
                "count": 0,
                "items": [],
                "error": normalize_text(str(exc)),
                "note": "",
                "html_snapshot": "",
            }
            payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
            payload["cache_hit"] = False
            payload["cached_age_seconds"] = 0.0
            payload["json_snapshot"] = self.artifacts.save_json(
                self.source,
                query,
                payload,
                force=True,
            )
            return payload
        finally:
            if driver is not None:
                self._release_driver(driver, acquired_headless)


class MercadoLivreScraper(BaseMarketplaceScraper):
    source = "mercadolivre"
    profile_name = "mercadolivre"
    open_wait_seconds = 2.0

    def build_search_url(self, query: str) -> str:
        search_query = build_xeon_search_query(query) if is_xeon_query(query) else query
        return f"https://lista.mercadolivre.com.br/{slugify(search_query)}"

    def is_page_ready(self, page_html: str, current_url: str) -> bool:
        lowered = page_html.lower()
        return (
            "ui-search-layout__item" in lowered
            or "hubo un error accediendo a esta pagina" in lowered
            or "poly-component__title" in lowered
        )

    def detect_error(self, page_title: str, page_html: str, current_url: str) -> str:
        lowered = page_html.lower()
        if "hubo un error accediendo a esta pagina" in lowered:
            return "Mercado Livre devolveu uma pagina de erro."
        return ""

    def parse_items(self, page_html: str, max_results: int) -> list[Listing]:
        soup = make_soup(
            page_html,
            parse_only=SoupStrainer("li", class_="ui-search-layout__item"),
        )
        cards = soup.find_all("li", class_="ui-search-layout__item")
        items: list[Listing] = []
        seen_urls: set[str] = set()

        for card in cards:
            title_link = card.select_one("a.poly-component__title")
            if not title_link:
                continue

            url = title_link.get("href", "").strip()
            if not url or url in seen_urls:
                continue

            title = normalize_text(title_link.get_text(" ", strip=True))
            current_fraction = first_matching_text(
                card.select("div.poly-price__current span.andes-money-amount__fraction")
            )
            current_cents = first_matching_text(
                card.select("div.poly-price__current span.andes-money-amount__cents")
            )
            price = format_brl(current_fraction, current_cents)
            installment = first_matching_text(card.select("span.poly-price__installments"))
            old_fraction = first_matching_text(card.select("s span.andes-money-amount__fraction"))
            shipping = ""
            raw_text = normalize_text(card.get_text(" ", strip=True))

            if "Frete gratis" in raw_text or "Frete grátis" in raw_text:
                shipping = "Frete gratis"

            items.append(
                Listing(
                    source=self.source,
                    title=title,
                    price=price or (f"R$ {old_fraction}" if old_fraction else ""),
                    price_value=parse_price_value(price or (f"R$ {old_fraction}" if old_fraction else "")),
                    url=url,
                    installment=installment,
                    shipping=shipping,
                    image=extract_image(card),
                    raw_text=raw_text[:450],
                )
            )
            seen_urls.add(url)

            if len(items) >= max_results:
                break

        return items


class OLXScraper(BaseMarketplaceScraper):
    source = "olx"
    profile_name = "olx"
    open_wait_seconds = 2.4

    def build_search_url(self, query: str) -> str:
        return f"https://www.olx.com.br/brasil?q={quote_plus(query)}&sf=1"

    def is_page_ready(self, page_html: str, current_url: str) -> bool:
        lowered = page_html.lower()
        return (
            "section.olx-adcard" in lowered
            or 'data-testid="adcard-link"' in lowered
            or 'id="__next_data__"' in lowered
            or "attention required" in lowered
            or "sorry, you have been blocked" in lowered
        )

    def detect_error(self, page_title: str, page_html: str, current_url: str) -> str:
        title = page_title.lower()
        lowered = page_html.lower()
        if "attention required" in title:
            return "OLX bloqueou a automacao nesta tentativa."
        if "sorry, you have been blocked" in lowered:
            return "OLX bloqueou a automacao nesta tentativa."
        return ""

    def should_allow_soft_query_match(
        self,
        query: str,
        item: Listing,
        resolved_category: str,
    ) -> bool:
        return matches_soft_console_query(query, item)

    def post_filter_reason(
        self,
        query: str,
        item: Listing,
        resolved_category: str,
    ) -> str:
        if looks_like_switch_service_listing(query, item):
            return "category_mismatch"
        return ""

    def _extract_next_data_ads(self, page_html: str) -> list[dict[str, Any]]:
        match = R_NEXT_DATA_SCRIPT.search(page_html)
        if not match:
            return []

        payload_text = match.group(1)
        for candidate in (payload_text, html_unescape(payload_text)):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            ads = payload.get("props", {}).get("pageProps", {}).get("ads", [])
            if isinstance(ads, list):
                return [ad for ad in ads if isinstance(ad, dict)]
            break

        return []

    def _normalize_item_url(self, value: Any) -> str:
        raw_url = normalize_text(str(value or ""))
        if not raw_url:
            return ""
        return urljoin("https://www.olx.com.br", raw_url)

    def _format_posted_at(self, value: Any) -> str:
        if value in (None, ""):
            return ""

        if isinstance(value, str) and not value.isdigit():
            return normalize_text(value)

        try:
            timestamp = int(value)
        except (TypeError, ValueError):
            return normalize_text(str(value))

        if timestamp <= 0:
            return ""

        try:
            return time.strftime("%d/%m %H:%M", time.localtime(timestamp))
        except (OverflowError, OSError, ValueError):
            return ""

    def _extract_shipping_badges(self, ad: dict[str, Any]) -> str:
        olx_pay = ad.get("olxPay")
        if not isinstance(olx_pay, dict):
            return ""

        badges: list[str] = []
        for badge in olx_pay.get("transactionalBadges") or []:
            if not isinstance(badge, dict):
                continue
            text = normalize_text(str(badge.get("text") or ""))
            if text and text not in badges:
                badges.append(text)

        return " | ".join(badges)

    def _extract_installment_label(self, ad: dict[str, Any]) -> str:
        olx_pay = ad.get("olxPay")
        if not isinstance(olx_pay, dict):
            return ""

        installments = olx_pay.get("installments")
        if not isinstance(installments, list):
            return ""

        chosen: dict[str, Any] | None = None
        for installment in installments:
            if not isinstance(installment, dict):
                continue
            if installment.get("highlighted"):
                chosen = installment
                break

        if chosen is None:
            for installment in installments:
                if not isinstance(installment, dict):
                    continue
                if installment.get("times") and (installment.get("price") or {}).get("label"):
                    chosen = installment
                    break

        if not chosen:
            return ""

        try:
            times = int(chosen.get("times") or 0)
        except (TypeError, ValueError):
            return ""

        if times <= 1:
            return ""

        price_label = normalize_text(str((chosen.get("price") or {}).get("label") or ""))
        if not price_label:
            return ""

        fee_raw = (chosen.get("fee") or {}).get("raw")
        suffix = ""
        if isinstance(fee_raw, (int, float)) and fee_raw <= 0:
            suffix = " sem juros"

        return f"{times}x de {price_label}{suffix}".strip()

    def _build_raw_text(
        self,
        ad: dict[str, Any],
        title: str,
        price: str,
        location: str,
        posted_at: str,
        installment: str,
        shipping: str,
    ) -> str:
        parts = [
            title,
            price,
            location,
            posted_at,
            normalize_text(str(ad.get("categoryName") or "")),
            installment,
            shipping,
        ]

        for prop in ad.get("properties") or []:
            if not isinstance(prop, dict):
                continue
            label = normalize_text(str(prop.get("label") or ""))
            value = normalize_text(str(prop.get("value") or ""))
            if label and value:
                parts.append(f"{label}: {value}")
            elif value:
                parts.append(value)

        return normalize_text(" ".join(part for part in parts if part))[:450]

    def _parse_next_data_items(self, page_html: str, max_results: int) -> list[Listing]:
        items: list[Listing] = []
        seen_urls: set[str] = set()

        for ad in self._extract_next_data_ads(page_html):
            title = normalize_text(str(ad.get("subject") or ad.get("title") or ""))
            if not title:
                continue

            url = self._normalize_item_url(ad.get("friendlyUrl") or ad.get("url"))
            if not url or url in seen_urls:
                continue

            price = normalize_text(str(ad.get("priceValue") or ad.get("price") or ""))
            price_value = parse_price_value(price)
            if price_value is None:
                raw_price = ad.get("price")
                if isinstance(raw_price, (int, float)):
                    price_value = float(raw_price)
                    if not price:
                        price = format_brl_value(price_value)

            location = normalize_text(str(ad.get("location") or ""))
            posted_at = self._format_posted_at(ad.get("date") or ad.get("origListTime"))
            installment = self._extract_installment_label(ad)
            shipping = self._extract_shipping_badges(ad)

            image = ""
            images = ad.get("images")
            if isinstance(images, list) and images:
                first_image = images[0]
                if isinstance(first_image, dict):
                    image = normalize_text(
                        str(first_image.get("originalWebp") or first_image.get("original") or "")
                    )

            items.append(
                Listing(
                    source=self.source,
                    title=title,
                    price=price,
                    price_value=price_value,
                    url=url,
                    location=location,
                    posted_at=posted_at,
                    installment=installment,
                    shipping=shipping,
                    image=image,
                    raw_text=self._build_raw_text(
                        ad,
                        title,
                        price,
                        location,
                        posted_at,
                        installment,
                        shipping,
                    ),
                )
            )
            seen_urls.add(url)

            if len(items) >= max_results:
                break

        return items

    def parse_items(self, page_html: str, max_results: int) -> list[Listing]:
        next_data_items = self._parse_next_data_items(page_html, max_results)
        if next_data_items:
            return next_data_items

        soup = make_soup(
            page_html,
            parse_only=SoupStrainer("section", class_="olx-adcard"),
        )
        cards = soup.find_all("section", class_="olx-adcard")
        items: list[Listing] = []
        seen_urls: set[str] = set()

        for card in cards:
            title_link = card.select_one('a[data-testid="adcard-link"]')
            if not title_link:
                continue

            title = normalize_text(title_link.get("title") or title_link.get_text(" ", strip=True))
            url = title_link.get("href", "").strip()
            if not title or not url or url in seen_urls:
                continue

            price_nodes = card.select('[class*="price"], [class*="Price"]')
            location_nodes = card.select('[class*="location"], [class*="Location"]')
            date_nodes = card.select('[class*="date"], [class*="Date"]')

            price = first_matching_text(price_nodes, R_CURRENCY)
            installment = ""
            for node in price_nodes:
                text = normalize_text(node.get_text(" ", strip=True))
                if "x de" in text or "sem juros" in text:
                    installment = text
                    break

            location = ""
            if len(location_nodes) > 1:
                location = normalize_text(location_nodes[-1].get_text(" ", strip=True))
            elif location_nodes:
                location = normalize_text(location_nodes[0].get_text(" ", strip=True))
                location = re.sub(r"\s+Hoje,.*$", "", location).strip()
                location = re.sub(r"\s+Ontem,.*$", "", location).strip()

            posted_at = first_matching_text(date_nodes)

            items.append(
                Listing(
                    source=self.source,
                    title=title,
                    price=price,
                    price_value=parse_price_value(price),
                    url=url,
                    location=location,
                    posted_at=posted_at,
                    installment=installment,
                    image=extract_image(card),
                    raw_text=normalize_text(card.get_text(" ", strip=True))[:450],
                )
            )
            seen_urls.add(url)

            if len(items) >= max_results:
                break

        return items


class KabumScraper(BaseMarketplaceScraper):
    source = "kabum"
    profile_name = "kabum"
    open_wait_seconds = 2.2

    def build_search_url(self, query: str) -> str:
        return f"https://www.kabum.com.br/busca/{slugify(query)}"

    def is_page_ready(self, page_html: str, current_url: str) -> bool:
        lowered = page_html.lower()
        return (
            'id="__next_data__"' in lowered
            or '"catalogserver"' in lowered
            or 'id="productschema"' in lowered
        )

    def detect_error(self, page_title: str, page_html: str, current_url: str) -> str:
        lowered = page_html.lower()
        if "acesso negado" in lowered or "access denied" in lowered:
            return "KaBuM bloqueou a automacao nesta tentativa."
        return ""

    def _product_url(self, product: dict[str, Any]) -> str:
        code = product.get("code")
        friendly_name = product.get("friendlyName") or slugify(product.get("name", ""))
        if code:
            return f"https://www.kabum.com.br/produto/{code}/{friendly_name}"
        return ""

    def _extract_products(self, page_html: str) -> list[dict[str, Any]]:
        soup = make_soup(page_html, parse_only=SoupStrainer("script"))
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data and next_data.string:
            try:
                payload = json.loads(next_data.string)
                return (
                    payload.get("props", {})
                    .get("pageProps", {})
                    .get("data", {})
                    .get("catalogServer", {})
                    .get("data", [])
                )
            except json.JSONDecodeError:
                pass

        product_schema = soup.find("script", id="productSchema")
        if product_schema and product_schema.string:
            try:
                items = json.loads(product_schema.string)
            except json.JSONDecodeError:
                return []
            extracted = []
            for item in items:
                extracted.append(
                    {
                        "name": item.get("name", ""),
                        "image": item.get("image", ""),
                        "friendlyName": slugify(item.get("name", "")),
                        "priceWithDiscount": parse_price_value(
                            format_brl_value(
                                item.get("offers", {})
                                .get("priceSpecification", {})
                                .get("price")
                            )
                        ),
                        "maxInstallment": "",
                        "code": "",
                        "sellerName": item.get("brand", {}).get("name", ""),
                        "category": item.get("category", ""),
                        "available": True,
                    }
                )
            return extracted
        return []

    def parse_items(self, page_html: str, max_results: int) -> list[Listing]:
        items: list[Listing] = []
        seen_urls: set[str] = set()

        for product in self._extract_products(page_html):
            title = normalize_text(product.get("name", ""))
            if not title:
                continue

            url = self._product_url(product)
            if url in seen_urls:
                continue

            available = product.get("available")
            if available is False:
                continue

            price_value = None
            for field in ("priceWithDiscount", "price", "priceMarketplace", "oldPrice"):
                raw_value = product.get(field)
                if raw_value in (None, "", 0):
                    continue
                try:
                    price_value = float(raw_value)
                    break
                except (TypeError, ValueError):
                    continue

            price = format_brl_value(price_value)
            installment = normalize_text(product.get("maxInstallment", ""))
            seller_name = normalize_text(product.get("sellerName", ""))
            category_name = normalize_text(product.get("category", ""))
            raw_text = normalize_text(
                " ".join(
                    part
                    for part in (
                        title,
                        seller_name,
                        category_name,
                        installment,
                    )
                    if part
                )
            )

            items.append(
                Listing(
                    source=self.source,
                    title=title,
                    price=price,
                    price_value=price_value,
                    url=url,
                    installment=installment,
                    image=product.get("image", "") or product.get("thumbnail", ""),
                    raw_text=raw_text[:450],
                )
            )
            if url:
                seen_urls.add(url)

            if len(items) >= max_results:
                break

        return items


class TerabyteScraper(BaseMarketplaceScraper):
    source = "terabyte"
    profile_name = "terabyte"
    open_wait_seconds = 2.5

    def build_search_url(self, query: str) -> str:
        return f"https://www.terabyteshop.com.br/busca?str={quote_plus(query)}"

    def is_page_ready(self, page_html: str, current_url: str) -> bool:
        lowered = page_html.lower()
        return (
            'class="product-item"' in lowered
            or "under attack mode" in lowered
            or "busca :" in lowered
        )

    def detect_error(self, page_title: str, page_html: str, current_url: str) -> str:
        lowered_title = page_title.lower()
        lowered = page_html.lower()
        if "under attack mode" in lowered_title or "under attack mode" in lowered:
            return "Terabyte ativou protecao anti-bot nesta tentativa."
        return ""

    def empty_results_note(self, page_html: str) -> str:
        lowered = page_html.lower()
        if "nenhum produto encontrado" in lowered:
            return "Terabyte carregou a busca, mas nao retornou produtos para esse termo."
        return ""

    def parse_items(self, page_html: str, max_results: int) -> list[Listing]:
        soup = make_soup(page_html, parse_only=SoupStrainer("div", class_="product-item"))
        cards = soup.find_all("div", class_="product-item")
        items: list[Listing] = []
        seen_urls: set[str] = set()

        for card in cards:
            title_link = card.find("a", class_="product-item__name")
            if not title_link:
                continue

            title = normalize_text(title_link.get("title") or title_link.get_text(" ", strip=True))
            url = title_link.get("href", "").strip()
            if not title or not url or url in seen_urls:
                continue

            price = first_matching_text(card.find_all("div", class_="product-item__new-price"), R_CURRENCY)
            installment = first_matching_text(card.find_all("div", class_="product-item__juros"))
            old_price = first_matching_text(card.find_all("div", class_="product-item__old-price"), R_CURRENCY)
            raw_text = normalize_text(card.get_text(" ", strip=True))

            items.append(
                Listing(
                    source=self.source,
                    title=title,
                    price=price or old_price,
                    price_value=parse_price_value(price or old_price),
                    url=url,
                    installment=installment,
                    image=extract_image(card),
                    raw_text=raw_text[:450],
                )
            )
            seen_urls.add(url)

        return items


class PCGamerBrasiliaScraper(BaseMarketplaceScraper):
    source = "pcgamerbrasilia"
    profile_name = "pcgamerbrasilia"
    open_wait_seconds = 2.4

    def build_search_url(self, query: str) -> str:
        return (
            f"{PC_GAMER_BRASILIA_BASE_URL}/produtos"
            f"?q={quote_plus(query)}&sort=price&limit=48"
        )

    def is_page_ready(self, page_html: str, current_url: str) -> bool:
        lowered = page_html.lower()
        return (
            'class="product-card' in lowered
            or "nenhum resultado encontrado" in lowered
            or "azion - default error page" in lowered
        )

    def detect_error(self, page_title: str, page_html: str, current_url: str) -> str:
        lowered_title = page_title.lower()
        lowered = page_html.lower()
        if "azion - default error page" in lowered_title or "azion - default error page" in lowered:
            return "PC Gamer Brasilia bloqueou a automacao nesta tentativa."
        return ""

    def empty_results_note(self, page_html: str) -> str:
        lowered = page_html.lower()
        if "nenhum resultado encontrado" in lowered:
            return "PC Gamer Brasilia carregou a busca, mas nao retornou produtos para esse termo."
        return ""

    def _extract_price_label(self, node: Any) -> tuple[str, str]:
        text = normalize_text(node.get_text(" ", strip=True))
        if not text:
            return "", ""

        match = R_CURRENCY.search(text)
        if not match:
            return "", text

        price = match.group(0)
        label = normalize_text(text.replace(price, ""))
        return price, label

    def parse_items(self, page_html: str, max_results: int) -> list[Listing]:
        soup = make_soup(page_html, parse_only=SoupStrainer("div", class_="product-card"))
        cards = [
            card
            for card in soup.find_all("div", class_="product-card")
            if card.get("data-product-name")
        ]
        items: list[Listing] = []
        seen_urls: set[str] = set()

        for card in cards:
            title = normalize_text(card.get("data-product-name", ""))
            title_link = card.select_one("a.product-link[href]")
            href = ""
            if title_link:
                href = title_link.get("href", "").strip()
            href = href or card.get("data-product-url", "").strip()
            if not title or not href:
                continue
            url = urljoin(PC_GAMER_BRASILIA_BASE_URL, href)

            if not url or url in seen_urls:
                continue

            stock_label = first_matching_text(card.select(".stock-label-overlay"))
            if "esgotado" in normalize_match_text(stock_label):
                continue

            pix_blocks = card.select(".product-card-price .pix .product-price-final")
            primary_price = ""
            primary_label = ""
            secondary_price = ""
            secondary_label = ""

            if pix_blocks:
                primary_price, primary_label = self._extract_price_label(pix_blocks[0])
            if len(pix_blocks) > 1:
                secondary_price, secondary_label = self._extract_price_label(pix_blocks[1])

            installment = first_matching_text(card.select(".installments"))
            price_display = primary_price
            if primary_price and primary_label:
                price_display = f"{primary_price} {primary_label}"
            elif not price_display:
                price_display = first_matching_text(card.select(".installments"), R_CURRENCY)

            raw_parts = [
                stock_label,
                title,
                price_display,
                installment,
            ]
            if secondary_price:
                raw_parts.append(
                    f"{secondary_label}: {secondary_price}" if secondary_label else secondary_price
                )

            items.append(
                Listing(
                    source=self.source,
                    title=title,
                    price=price_display,
                    price_value=parse_price_value(price_display),
                    url=url,
                    installment=installment,
                    image=extract_image(card),
                    raw_text=normalize_text(" ".join(part for part in raw_parts if part))[:450],
                )
            )
            seen_urls.add(url)

            if len(items) >= max_results:
                break

        return items


class AliExpressScraper(BaseMarketplaceScraper):
    source = "aliexpress"
    profile_name = "aliexpress"
    persistent_profile = True
    page_load_timeout_seconds = 45.0
    open_wait_seconds = 3.0
    challenge_wait_seconds = 35
    challenge_poll_seconds = 2
    detail_tax_wait_seconds = 3.0
    detail_tax_max_items = 10
    detail_tax_total_budget_seconds = 30.0
    detail_tax_cache_size = 256
    card_pattern = re.compile(
        r'<a[^>]*class="[^"]*search-card-item[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self, browser: ChromeFactory, artifacts: ArtifactStore) -> None:
        super().__init__(browser, artifacts)
        self._detail_tax_cache: OrderedDict[
            str, tuple[float | None, float | None, str]
        ] = OrderedDict()
        self._detail_tax_cache_lock = threading.Lock()

    def build_search_url(self, query: str) -> str:
        return f"{ALIEXPRESS_BASE_URL}/wholesale?SearchText={quote_plus(query)}"

    def _has_results(self, page_html: str) -> bool:
        lowered = page_html.lower()
        return 'id="card-list"' in lowered and "search-card-item" in lowered

    def _needs_challenge(self, page_title: str, page_html: str, current_url: str) -> bool:
        lowered_title = page_title.lower()
        lowered_html = page_html.lower()
        lowered_url = current_url.lower()
        return (
            "captcha interception" in lowered_title
            or "/_____tmd_____/" in lowered_url
            or "punishtextfetch" in lowered_html
            or "nc_1_nocaptcha" in lowered_html
        )

    def is_page_ready(self, page_html: str, current_url: str) -> bool:
        lowered = page_html.lower()
        return (
            self._has_results(page_html)
            or "/_____tmd_____/" in current_url.lower()
            or "captcha interception" in lowered
            or "sem resultados" in lowered
        )

    def detect_error(self, page_title: str, page_html: str, current_url: str) -> str:
        if self._needs_challenge(page_title, page_html, current_url):
            return (
                "AliExpress ativou captcha ou bloqueio nesta tentativa. Rode com headless "
                "desativado e, se a pagina pedir verificacao, conclua manualmente no navegador."
            )
        return ""

    def empty_results_note(self, page_html: str) -> str:
        lowered = page_html.lower()
        if "sem resultados" in lowered or "nenhum resultado" in lowered:
            return "AliExpress carregou a busca, mas nao retornou produtos para esse termo."
        return ""

    def format_driver_error(self, exc: WebDriverException) -> str:
        message = summarize_webdriver_message(exc).lower()
        if (
            "invalid session id" in message
            or "session deleted as the browser has closed the connection" in message
            or "not connected to devtools" in message
            or "disconnected:" in message
        ):
            return (
                "A sessao da AliExpress foi perdida porque a janela do Chrome foi fechada "
                "ou caiu durante a verificacao manual. Refaca a busca com headless "
                "desativado, mantenha a janela aberta e aguarde a requisicao terminar."
            )
        if self._is_renderer_timeout_error(message):
            return (
                "A pagina da AliExpress travou no Chrome durante o carregamento. "
                "O sistema pode tentar recuperar a busca automaticamente em segundo plano; "
                "se ainda falhar, refaca a tentativa em alguns segundos."
            )
        return super().format_driver_error(exc)

    def _is_renderer_timeout_error(self, error: Exception | str) -> bool:
        message = summarize_webdriver_message(error).lower()
        return (
            "timed out receiving message from renderer" in message
            or ("timeout" in message and "renderer" in message)
            or "travou no chrome durante o carregamento" in message
        )

    def _should_retry_in_headless(self, result: dict[str, Any], headless: bool) -> bool:
        if headless or result.get("success"):
            return False
        return self._is_renderer_timeout_error(str(result.get("error", "")))

    def search(
        self,
        query: str,
        max_results: int = 10,
        headless: bool = False,
        category: str = "auto",
        match_query: str | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        result = super().search(
            query=query,
            max_results=max_results,
            headless=headless,
            category=category,
            match_query=match_query,
        )
        if not self._should_retry_in_headless(result, headless):
            return result

        retry_result = super().search(
            query=query,
            max_results=max_results,
            headless=True,
            category=category,
            match_query=match_query,
        )
        if retry_result.get("success"):
            note_parts = [
                retry_result.get("note", ""),
                "AliExpress recuperou a busca automaticamente apos timeout do Chrome.",
            ]
            retry_result["note"] = "; ".join(part for part in note_parts if part)
            retry_result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
            retry_result["json_snapshot"] = self.artifacts.save_json(self.source, query, retry_result)
            return retry_result

        note_parts = [
            result.get("note", ""),
            "A busca tentou uma recuperacao automatica em segundo plano, mas o AliExpress continuou instavel.",
        ]
        result["note"] = "; ".join(part for part in note_parts if part)
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        result["json_snapshot"] = self.artifacts.save_json(
            self.source,
            query,
            result,
            force=not result.get("success", False),
        )
        return result

    def _normalize_price_label(self, value: str) -> str:
        text = normalize_text(html_unescape(value or ""))
        match = re.search(r"R\$\s*([\d\.]+)(?:\s*,\s*(\d{1,2}))?", text)
        if not match:
            return ""
        fraction, cents = match.groups()
        return format_brl(fraction, cents or "")

    def _build_item_href_map(self, page_html: str) -> dict[str, str]:
        href_map: dict[str, str] = {}
        for match in R_ALIEXPRESS_ITEM_HREF.finditer(page_html):
            href = html_unescape(match.group(1).strip())
            product_id = normalize_text(match.group(2))
            if not href or not product_id or product_id in href_map:
                continue
            href_map[product_id] = urljoin(ALIEXPRESS_BASE_URL, href)
        return href_map

    def _find_item_href(
        self,
        page_html: str,
        product_id: str,
        href_map: dict[str, str] | None = None,
    ) -> str:
        if not product_id:
            return ""

        if href_map:
            href = href_map.get(product_id)
            if href:
                return href

        match = re.search(
            rf'href="([^"]*{re.escape(product_id)}[^"]*)"',
            page_html,
            re.IGNORECASE,
        )
        if not match:
            return f"{ALIEXPRESS_BASE_URL}/item/{product_id}.html"

        return urljoin(ALIEXPRESS_BASE_URL, html_unescape(match.group(1).strip()))

    def _has_detail_tax_marker(self, page_html: str) -> bool:
        lowered = page_html.lower()
        return "impostos estimados" in lowered or "estimated tax" in lowered

    def _get_cached_detail_tax(
        self,
        url: str,
    ) -> tuple[float | None, float | None, str] | None:
        if not url:
            return None
        with self._detail_tax_cache_lock:
            cached = self._detail_tax_cache.get(url)
            if cached is None:
                return None
            self._detail_tax_cache.move_to_end(url)
            return cached

    def _set_cached_detail_tax(
        self,
        url: str,
        tax_percent: float | None,
        tax_value: float | None,
        tax_label: str,
    ) -> None:
        if not url or not tax_label:
            return
        with self._detail_tax_cache_lock:
            self._detail_tax_cache[url] = (tax_percent, tax_value, tax_label)
            self._detail_tax_cache.move_to_end(url)
            while len(self._detail_tax_cache) > self.detail_tax_cache_size:
                self._detail_tax_cache.popitem(last=False)

    def _build_import_tax_details(
        self,
        price_value: float | None,
        is_imported: bool | None,
        tax_rate: float | None,
    ) -> tuple[float | None, float | None, str]:
        if is_imported is not True:
            return None, None, ""

        if tax_rate is None or tax_rate <= 0:
            return None, None, ""

        tax_value = None
        if price_value is not None and tax_rate > 0:
            tax_value = round(price_value * (tax_rate / 100.0), 2)

        label = format_percent_value(tax_rate)
        if tax_value is not None:
            label = f"{label} (~{format_brl_value(tax_value)})"

        return tax_rate, tax_value, label

    def _extract_import_tax_from_detail_html(
        self,
        page_html: str,
        price_value: float | None,
    ) -> tuple[float | None, float | None, str]:
        if not page_html:
            return None, None, ""

        normalized_html = html_unescape(page_html)
        match = R_ALIEXPRESS_DETAIL_TAX_HTML.search(normalized_html)
        if not match:
            text = normalize_text(R_HTML_TAG.sub(" ", normalized_html))
            match = R_ALIEXPRESS_DETAIL_TAX_TEXT.search(text)
        else:
            text = ""

        if not match and self._has_detail_tax_marker(normalized_html):
            text = normalize_text(
                make_soup(normalized_html).get_text(" ", strip=True)
            )
            match = R_ALIEXPRESS_DETAIL_TAX_TEXT.search(text)
        if not match:
            return None, None, ""

        raw_tax_label = normalize_text(match.group(1))
        tax_value = parse_price_value(raw_tax_label)
        tax_percent = None
        if tax_value is not None and price_value not in (None, 0):
            tax_percent = round((tax_value / float(price_value)) * 100.0, 1)

        tax_label = format_brl_value(tax_value) if tax_value is not None else raw_tax_label
        pretty_label = f"{tax_label} estimados"
        if tax_percent is not None:
            pretty_label = f"{pretty_label} ({format_percent_value(tax_percent)})"

        return tax_percent, tax_value, pretty_label

    def _load_detail_page_for_tax(self, driver: webdriver.Chrome, url: str) -> str:
        driver.set_page_load_timeout(25)
        try:
            driver.get(url)
        except WebDriverException as exc:
            if not self._is_renderer_timeout_error(exc):
                raise
            try:
                driver.execute_script("window.stop();")
            except WebDriverException:
                pass
        deadline = time.time() + self.detail_tax_wait_seconds
        last_html = ""

        while time.time() < deadline:
            time.sleep(0.4)
            last_html = driver.page_source
            if self._has_detail_tax_marker(last_html):
                break

        return last_html or driver.page_source

    def _create_detail_tax_driver(self) -> webdriver.Chrome:
        # A fresh ephemeral session is more reliable here than reusing the
        # search session, which can remain unstable after the results page.
        return self.browser.create(
            f"{self.profile_name}-tax",
            headless=True,
            persistent_profile=False,
        )

    def post_process_items(
        self,
        items: list[Listing],
        headless: bool,
    ) -> list[Listing]:
        imported_items = [
            item
            for item in items
            if item.is_imported and item.url and not item.import_tax_label
        ]
        if not imported_items:
            return items

        pending_items = imported_items[: self.detail_tax_max_items]
        unresolved_items: list[Listing] = []
        for item in pending_items:
            cached = self._get_cached_detail_tax(item.url)
            if cached is None:
                unresolved_items.append(item)
                continue
            item.import_tax_percent, item.import_tax_value, item.import_tax_label = cached
            apply_import_tax_comparison_adjustment(item)

        if not unresolved_items:
            for item in items:
                apply_import_tax_comparison_adjustment(item)
            return items

        deadline = time.time() + self.detail_tax_total_budget_seconds

        driver: webdriver.Chrome | None = None
        attempted_items: list[Listing] = []

        try:
            # The detail pass runs in a clean session because the search session can stay
            # unstable after AliExpress challenge/redirect flows and silently drop the tax.
            driver = self._create_detail_tax_driver()

            for item in unresolved_items:
                if time.time() >= deadline:
                    break

                attempted_items.append(item)
                page_html = self._load_detail_page_for_tax(driver, item.url)
                tax_percent, tax_value, tax_label = self._extract_import_tax_from_detail_html(
                    page_html,
                    item.price_value,
                )
                if tax_label:
                    item.import_tax_percent = tax_percent
                    item.import_tax_value = tax_value
                    item.import_tax_label = tax_label
                    self._set_cached_detail_tax(item.url, tax_percent, tax_value, tax_label)
                    apply_import_tax_comparison_adjustment(item)
                    continue

                if item.import_tax_label:
                    apply_import_tax_comparison_adjustment(item)
                    continue

                item.import_tax_percent = None
                item.import_tax_value = None
                item.import_tax_label = "Nao informado pelo AliExpress"
                self._set_cached_detail_tax(
                    item.url,
                    item.import_tax_percent,
                    item.import_tax_value,
                    item.import_tax_label,
                )
                apply_import_tax_comparison_adjustment(item)
        except WebDriverException:
            for item in attempted_items or unresolved_items:
                if not item.import_tax_label:
                    item.import_tax_label = "Nao foi possivel ler a taxa"
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

        for item in items:
            apply_import_tax_comparison_adjustment(item)

        return items

    def _parse_structured_items(self, page_html: str, max_results: int) -> list[Listing]:
        raw_items = extract_json_array_after_marker(page_html, '"itemList":{"content":')
        if not raw_items:
            return []

        href_map = self._build_item_href_map(page_html)
        items: list[Listing] = []
        seen_urls: set[str] = set()
        seen_product_ids: set[str] = set()

        for raw_item in raw_items:
            title = normalize_text(str(raw_item.get("title", {}).get("displayTitle", "")))
            product_id = normalize_text(str(raw_item.get("productId", "")))
            if not title or not product_id:
                continue
            canonical_product_id = normalize_text(
                str(raw_item.get("redirectedId") or raw_item.get("productId") or "")
            )
            if canonical_product_id and canonical_product_id in seen_product_ids:
                continue

            url = self._find_item_href(page_html, canonical_product_id or product_id, href_map=href_map)
            if not url or url in seen_urls:
                continue

            prices = raw_item.get("prices", {}) if isinstance(raw_item.get("prices"), dict) else {}
            sale_price = prices.get("salePrice", {}) if isinstance(prices.get("salePrice"), dict) else {}
            original_price = (
                prices.get("originalPrice", {})
                if isinstance(prices.get("originalPrice"), dict)
                else {}
            )

            price = normalize_text(
                str(
                    sale_price.get("formattedPrice")
                    or original_price.get("formattedPrice")
                    or ""
                )
            )
            price_value = parse_optional_float(sale_price.get("minPrice"))
            if price_value is None:
                price_value = parse_optional_float(original_price.get("minPrice"))
            if price_value is None:
                price_value = parse_price_value(price)

            trace = raw_item.get("trace", {}) if isinstance(raw_item.get("trace"), dict) else {}
            pdp_params = (
                trace.get("pdpParams", {})
                if isinstance(trace.get("pdpParams"), dict)
                else {}
            )
            trace_payload = parse_aliexpress_trace_payload(str(pdp_params.get("pdp_cdi", "")))
            ship_from_code = normalize_aliexpress_ship_from(str(trace_payload.get("shipFrom", "")))
            if not ship_from_code and has_aliexpress_local_flag(raw_item):
                ship_from_code = "BR"
            shipping_origin = aliexpress_shipping_origin_label(ship_from_code)
            is_imported = ship_from_code != "BR" if ship_from_code else None

            evaluation = (
                raw_item.get("evaluation", {})
                if isinstance(raw_item.get("evaluation"), dict)
                else {}
            )
            trade = raw_item.get("trade", {}) if isinstance(raw_item.get("trade"), dict) else {}
            trace_ut_log_map = (
                trace.get("utLogMap", {})
                if isinstance(trace.get("utLogMap"), dict)
                else {}
            )
            image_payload = (
                raw_item.get("image", {})
                if isinstance(raw_item.get("image"), dict)
                else {}
            )
            rating = normalize_rating_value(evaluation.get("starRating"))
            if rating is None:
                rating = normalize_rating_value(trace_payload.get("star"))

            sold_label = normalize_text(str(trade.get("tradeDesc", "")))
            sold_count = parse_optional_int(trace_ut_log_map.get("real_trade_count"))
            if sold_count is None:
                sold_count = parse_optional_int(trace_payload.get("order"))
            if sold_count is not None and sold_count < 0:
                sold_count = None

            tax_rate, tax_value, tax_label = self._build_import_tax_details(
                price_value=price_value,
                is_imported=is_imported,
                tax_rate=parse_optional_float(prices.get("taxRate")),
            )

            image = normalize_text(str(image_payload.get("imgUrl", "")))
            if image.startswith("//"):
                image = f"https:{image}"
            elif image.startswith("/"):
                image = urljoin(ALIEXPRESS_BASE_URL, image)

            raw_parts = [
                title,
                price,
                f"{rating:.1f}" if rating is not None else "",
                sold_label,
                shipping_origin,
                tax_label,
            ]

            listing = Listing(
                source=self.source,
                title=title,
                price=price,
                price_value=price_value,
                rating=rating,
                sold_count=sold_count,
                sold_label=sold_label,
                url=url,
                shipping_origin=shipping_origin,
                shipping_origin_code=ship_from_code,
                is_imported=is_imported,
                import_tax_percent=tax_rate,
                import_tax_value=tax_value,
                import_tax_label=tax_label,
                image=image,
                raw_text=normalize_text(" ".join(part for part in raw_parts if part))[:450],
            )
            items.append(apply_import_tax_comparison_adjustment(listing))
            seen_urls.add(url)
            if canonical_product_id:
                seen_product_ids.add(canonical_product_id)

            if len(items) >= max_results:
                break

        return items

    def after_load(
        self,
        driver: webdriver.Chrome,
        search_url: str,
        headless: bool,
        page_title: str,
        page_html: str,
        current_url: str,
    ) -> tuple[str, str, str]:
        if not self._needs_challenge(page_title, page_html, current_url):
            return page_title, page_html, current_url

        if headless:
            return page_title, page_html, current_url

        deadline = time.time() + self.challenge_wait_seconds

        while time.time() < deadline:
            time.sleep(self.challenge_poll_seconds)
            current_url = driver.current_url
            page_title = driver.title or ""
            page_html = driver.page_source

            if self._needs_challenge(page_title, page_html, current_url):
                continue

            if not self._has_results(page_html):
                driver.get(search_url)
                self._load_page(driver)
                current_url = driver.current_url
                page_title = driver.title or ""
                page_html = driver.page_source

            return page_title, page_html, current_url

        return page_title, page_html, current_url

    def parse_items(self, page_html: str, max_results: int) -> list[Listing]:
        structured_items = self._parse_structured_items(page_html, max_results)
        if structured_items:
            return structured_items

        items: list[Listing] = []
        seen_urls: set[str] = set()

        for match in self.card_pattern.finditer(page_html):
            href = html_unescape(match.group(1).strip())
            snippet = f'<a href="{href}">{match.group(2)}</a>'
            soup = BeautifulSoup(snippet, "html.parser")
            title_node = soup.select_one('[role="heading"]')
            title = normalize_text(
                (title_node.get("aria-label") if title_node else "")
                or (title_node.get("title") if title_node else "")
                or (title_node.get_text(" ", strip=True) if title_node else "")
            )
            if not title or not href:
                continue

            url = urljoin(ALIEXPRESS_BASE_URL, href)
            if not url or url in seen_urls:
                continue

            price_node = soup.select_one('div[aria-label^="R$"]')
            price = self._normalize_price_label(
                price_node.get("aria-label", "") if price_node else ""
            )
            if not price:
                price = self._normalize_price_label(normalize_text(soup.get_text(" ", strip=True)))

            image = extract_image(soup)
            if image.startswith("//"):
                image = f"https:{image}"
            elif image.startswith("/"):
                image = urljoin(ALIEXPRESS_BASE_URL, image)

            raw_text = normalize_text(soup.get_text(" ", strip=True))

            items.append(
                Listing(
                    source=self.source,
                    title=title,
                    price=price,
                    price_value=parse_price_value(price),
                    url=url,
                    image=image,
                    raw_text=raw_text[:450],
                )
            )
            seen_urls.add(url)

            if len(items) >= max_results:
                break

        return items

    def sort_filtered_items(self, query: str, items: list[Listing]) -> list[Listing]:
        def sort_key(item: Listing) -> tuple[bool, float, bool, float, bool, int, int]:
            effective_price = listing_effective_price_value(item)
            return (
                effective_price is None,
                effective_price if effective_price is not None else float("inf"),
                item.rating is None,
                -(item.rating or 0.0),
                item.sold_count is None,
                -(item.sold_count or 0),
                len(item.title),
            )

        return sorted(
            items,
            key=sort_key,
        )


class FacebookMarketplaceScraper(BaseMarketplaceScraper):
    source = "facebook"
    profile_name = "facebook"
    persistent_profile = True
    open_wait_seconds = 2.1
    login_wait_seconds = 180
    login_poll_seconds = 2
    scroll_passes = 6
    scroll_wait_seconds = 1.0
    scroll_stable_passes = 2

    def build_search_url(self, query: str) -> str:
        return (
            "https://www.facebook.com/marketplace/"
            f"{SETTINGS.facebook_region_slug or FACEBOOK_DEFAULT_REGION_SLUG}/search/?query={quote_plus(query)}"
        )

    def _has_marketplace_surface(self, page_html: str) -> bool:
        lowered = page_html.lower()
        return (
            "resultados da pesquisa" in lowered
            or "nenhum classificado encontrado" in lowered
            or "pesquisar no marketplace" in lowered
            or 'aria-label="coleção de itens do marketplace"' in lowered
            or "/marketplace/item/" in lowered
        )

    def _needs_login(self, page_html: str, current_url: str) -> bool:
        lowered_url = current_url.lower()
        if "/login" in lowered_url:
            return True
        if "/marketplace/" in lowered_url and self._has_marketplace_surface(page_html):
            return False

        return R_FACEBOOK_LOGIN_INPUT.search(page_html) is not None

    def is_page_ready(self, page_html: str, current_url: str) -> bool:
        lowered = page_html.lower()
        return (
            self._has_marketplace_surface(page_html)
            or "/marketplace/item/" in lowered
            or "/login" in current_url.lower()
        )

    def detect_error(self, page_title: str, page_html: str, current_url: str) -> str:
        if self._needs_login(page_html, current_url):
            return (
                "Facebook Marketplace exige login. Rode com headless desativado e use o "
                f"perfil salvo em {PROFILE_ROOT / 'facebook'} para autenticar manualmente."
            )
        return ""

    def empty_results_note(self, page_html: str) -> str:
        lowered = page_html.lower()
        if "nenhum classificado encontrado" in lowered:
            return "Facebook Marketplace carregou, mas retornou pagina sem resultados para a localizacao atual."
        return ""

    def format_driver_error(self, exc: WebDriverException) -> str:
        message = normalize_text(str(exc)).lower()
        if (
            "invalid session id" in message
            or "session deleted as the browser has closed the connection" in message
            or "not connected to devtools" in message
            or "disconnected:" in message
        ):
            return (
                "A sessao do Facebook foi perdida porque a janela do Chrome foi fechada "
                "ou desconectou durante o login manual. Refaca a busca com headless "
                "desativado, mantenha a janela aberta e aguarde a requisicao terminar."
            )
        return super().format_driver_error(exc)

    def _expand_results(
        self,
        driver: webdriver.Chrome,
        page_html: str,
    ) -> str:
        stable_passes = 0
        previous_count = page_html.count("/marketplace/item/")
        latest_html = page_html

        for _ in range(self.scroll_passes):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.scroll_wait_seconds)
            latest_html = driver.page_source
            current_count = latest_html.count("/marketplace/item/")
            if current_count <= previous_count:
                stable_passes += 1
                if stable_passes >= self.scroll_stable_passes:
                    break
            else:
                previous_count = current_count
                stable_passes = 0

        return latest_html

    def should_allow_soft_query_match(
        self,
        query: str,
        item: Listing,
        resolved_category: str,
    ) -> bool:
        return matches_soft_console_query(query, item)

    def post_filter_reason(
        self,
        query: str,
        item: Listing,
        resolved_category: str,
    ) -> str:
        if looks_like_switch_service_listing(query, item):
            return "category_mismatch"
        return ""

    def after_load(
        self,
        driver: webdriver.Chrome,
        search_url: str,
        headless: bool,
        page_title: str,
        page_html: str,
        current_url: str,
    ) -> tuple[str, str, str]:
        if headless or not self._needs_login(page_html, current_url):
            page_html = self._expand_results(driver, page_html)
            return page_title, page_html, current_url

        deadline = time.time() + self.login_wait_seconds

        while time.time() < deadline:
            time.sleep(self.login_poll_seconds)
            current_url = driver.current_url
            page_title = driver.title or ""
            page_html = driver.page_source

            if self._needs_login(page_html, current_url):
                continue

            if "/marketplace/search/" not in current_url:
                driver.get(search_url)
                self._load_page(driver)
                current_url = driver.current_url
                page_title = driver.title or ""
                page_html = driver.page_source

            page_html = self._expand_results(driver, page_html)
            return page_title, page_html, current_url

        page_html = self._expand_results(driver, page_html)
        return page_title, page_html, current_url

    def parse_items(self, page_html: str, max_results: int) -> list[Listing]:
        soup = BeautifulSoup(page_html, "html.parser")
        anchors = soup.select('a[href*="/marketplace/item/"]')
        items: list[Listing] = []
        seen_urls: set[str] = set()

        for anchor in anchors:
            url = anchor.get("href", "").strip()
            if not url or url in seen_urls:
                continue

            title = normalize_text(anchor.get_text(" ", strip=True))
            if not title:
                title = normalize_text(anchor.get("aria-label", ""))

            container = anchor
            for _ in range(4):
                if getattr(container, "parent", None) is None:
                    break
                container = container.parent

            raw_text = normalize_text(container.get_text(" ", strip=True))
            price_match = R_CURRENCY.search(raw_text)
            price = price_match.group(0) if price_match else ""

            if not title and not price:
                continue

            items.append(
                Listing(
                    source=self.source,
                    title=title or "Resultado do Facebook Marketplace",
                    price=price,
                    price_value=parse_price_value(price),
                    url=url,
                    image=extract_image(container),
                    raw_text=raw_text[:450],
                )
            )
            seen_urls.add(url)

            if len(items) >= max_results:
                break

        return items

class MarketplaceService:
    def __init__(self) -> None:
        browser = ChromeFactory()
        artifacts = ArtifactStore()
        self.artifacts = artifacts
        self.cache = SearchCache()
        self.scrapers = {
            "olx": OLXScraper(browser, artifacts),
            "mercadolivre": MercadoLivreScraper(browser, artifacts),
            "kabum": KabumScraper(browser, artifacts),
            "terabyte": TerabyteScraper(browser, artifacts),
            "pcgamerbrasilia": PCGamerBrasiliaScraper(browser, artifacts),
            "aliexpress": AliExpressScraper(browser, artifacts),
            "facebook": FacebookMarketplaceScraper(browser, artifacts),
        }

    def available_platforms(self) -> list[str]:
        return list(self.scrapers.keys())

    def _cache_key(
        self,
        platform: str,
        query: str,
        category: str,
        max_results: int,
        headless: bool,
    ) -> tuple[str, str, str, int, bool]:
        return (
            platform,
            normalize_match_text(query),
            normalize_category_name(category),
            max_results,
            headless,
        )

    def _search_platform_once(
        self,
        platform: str,
        query: str,
        match_query: str,
        max_results: int,
        headless: bool,
        category: str,
    ) -> dict[str, Any]:
        cache_key = self._cache_key(platform, query, category, max_results, headless)
        cached = self.cache.get(cache_key)
        if cached is not None:
            cached["query"] = match_query
            cached["search_term"] = query
            return cached

        scraper = self.scrapers[platform]
        result = scraper.search(
            query=query,
            match_query=match_query,
            max_results=max_results,
            headless=headless,
            category=category,
        )
        if result.get("success"):
            self.cache.set(cache_key, result)
        return result

    def _merge_platform_results(
        self,
        query: str,
        category: str,
        max_results: int,
        attempts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        successful = [attempt for attempt in attempts if attempt.get("success")]
        if not successful:
            result = clone_search_payload(attempts[0])
            result["search_terms_used"] = dedupe_terms(
                [attempt.get("search_term", "") for attempt in attempts]
            )
            result["search_attempts"] = [
                {
                    "search_term": attempt.get("search_term", ""),
                    "count": attempt.get("count", 0),
                    "success": attempt.get("success", False),
                }
                for attempt in attempts
            ]
            result["cache_hit"] = all(attempt.get("cache_hit", False) for attempt in attempts)
            result["cached_age_seconds"] = max(
                (float(attempt.get("cached_age_seconds", 0.0)) for attempt in attempts),
                default=0.0,
            )
            return result

        if len(successful) == 1:
            result = clone_search_payload(successful[0])
            result["search_terms_used"] = dedupe_terms([result.get("search_term", "")])
            result["search_attempts"] = [
                {
                    "search_term": attempt.get("search_term", ""),
                    "count": attempt.get("count", 0),
                    "success": attempt.get("success", False),
                }
                for attempt in attempts
            ]
            if len(attempts) > 1:
                result["note"] = "; ".join(
                    part
                    for part in (
                        result.get("note", ""),
                        "Busca automatica tentou variacoes adicionais da consulta.",
                    )
                    if part
                )
            result["cache_hit"] = all(attempt.get("cache_hit", False) for attempt in attempts)
            result["cached_age_seconds"] = max(
                (float(attempt.get("cached_age_seconds", 0.0)) for attempt in attempts),
                default=0.0,
            )
            return result

        best = max(successful, key=lambda item: (item.get("count", 0), item.get("matched_count", 0)))
        merged_items: dict[str, dict[str, Any]] = {}

        for attempt in successful:
            for raw_item in attempt.get("items", []):
                if not isinstance(raw_item, dict):
                    continue
                key = raw_item.get("url", "").strip() or (
                    f"{compact_text(str(raw_item.get('title', '')))}|"
                    f"{raw_item.get('price', '')}|"
                    f"{normalize_match_text(str(raw_item.get('location', '')))}"
                )
                existing = merged_items.get(key)
                if existing is None:
                    merged_items[key] = raw_item
                    continue

                existing_price = item_price_value(existing, comparison=True)
                current_price = item_price_value(raw_item, comparison=True)

                if existing_price is None and current_price is not None:
                    merged_items[key] = raw_item
                    continue

                if (
                    existing_price is not None
                    and current_price is not None
                    and current_price < existing_price
                ):
                    merged_items[key] = raw_item
                    continue

                if len(str(raw_item.get("title", ""))) < len(str(existing.get("title", ""))):
                    merged_items[key] = raw_item

        source = normalize_text(str(best.get("source", "")))
        scraper = self.scrapers.get(source)
        merged_values = [Listing(**item) for item in merged_items.values()]
        if scraper is not None:
            items = scraper.sort_filtered_items(query, merged_values)[:max_results]
        else:
            items = sort_items_for_query(query, merged_values)[:max_results]
        discarded = {
            "query_mismatch": 0,
            "blocked_term": 0,
            "bundle_term": 0,
            "category_mismatch": 0,
            "variant_mismatch": 0,
        }
        for attempt in successful:
            attempt_stats = attempt.get("stats") or {}
            attempt_discarded = attempt_stats.get("discarded_reasons") or {}
            for reason in discarded:
                discarded[reason] += int(attempt_discarded.get(reason, 0))

        merged = clone_search_payload(best)
        merged_stats = build_price_stats(items)
        merged_stats["resolved_category"] = resolve_category(query, category)
        merged_stats["scanned_items"] = sum(
            int((attempt.get("stats") or {}).get("scanned_items", 0))
            for attempt in successful
        )
        merged_stats["matched_items"] = len(items)
        merged_stats["discarded_titles"] = sum(
            int((attempt.get("stats") or {}).get("discarded_titles", 0))
            for attempt in successful
        )
        merged_stats["discarded_reasons"] = discarded

        merged["query"] = query
        merged["category"] = merged_stats["resolved_category"]
        merged["count"] = len(items)
        merged["matched_count"] = len(items)
        merged["scanned_count"] = merged_stats["scanned_items"]
        merged["items"] = [item.to_dict() for item in items]
        merged["stats"] = merged_stats
        merged["search_terms_used"] = dedupe_terms(
            [attempt.get("search_term", "") for attempt in successful]
        )
        merged["search_attempts"] = [
            {
                "search_term": attempt.get("search_term", ""),
                "count": attempt.get("count", 0),
                "success": attempt.get("success", False),
            }
            for attempt in attempts
        ]

        auto_note = (
            f"Busca automatica usou {len(merged['search_terms_used'])} variacoes da consulta."
            if len(merged["search_terms_used"]) > 1
            else ""
        )
        note_parts = [merged.get("note", ""), auto_note]
        merged["note"] = "; ".join(part for part in note_parts if part)
        merged["cache_hit"] = all(attempt.get("cache_hit", False) for attempt in attempts)
        merged["cached_age_seconds"] = max(
            (float(attempt.get("cached_age_seconds", 0.0)) for attempt in attempts),
            default=0.0,
        )
        return merged

    def search_platform(
        self,
        platform: str,
        query: str,
        max_results: int = 10,
        headless: bool = False,
        category: str = "auto",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        attempts: list[dict[str, Any]] = []
        search_candidates = build_search_candidates(query, category)
        resolved_category = resolve_category(query, category)
        target_count = determine_search_target_count(
            platform=platform,
            max_results=max_results,
            resolved_category=resolved_category,
        )
        min_attempts = 1
        if (
            platform in {"olx", "facebook"}
            and is_switch_console_query(query)
            and len(search_candidates) > 1
        ):
            min_attempts = min(3, len(search_candidates))

        for attempt_index, candidate in enumerate(search_candidates, start=1):
            result = self._search_platform_once(
                platform=platform,
                query=candidate,
                match_query=query,
                max_results=max_results,
                headless=headless,
                category=category,
            )
            attempts.append(result)
            if (
                result.get("success")
                and result.get("count", 0) >= target_count
                and attempt_index >= min_attempts
            ):
                break

        payload = self._merge_platform_results(
            query=query,
            category=category,
            max_results=max_results,
            attempts=attempts,
        )
        payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        payload["json_snapshot"] = self.artifacts.save_json(payload["source"], query, payload)
        return payload

    def search_many(
        self,
        query: str,
        platforms: list[str],
        max_results: int = 10,
        headless: bool = False,
        category: str = "auto",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        results: dict[str, Any] = {}
        total_items = 0
        worker_limit = min(len(platforms), 3 if headless else 2)

        if len(platforms) == 1:
            platform = platforms[0]
            results[platform] = self.search_platform(
                platform=platform,
                query=query,
                max_results=max_results,
                headless=headless,
                category=category,
            )
        else:
            collected: dict[str, Any] = {}
            with ThreadPoolExecutor(max_workers=worker_limit, thread_name_prefix="marketplace") as executor:
                future_map = {
                    executor.submit(
                        self.search_platform,
                        platform=platform,
                        query=query,
                        max_results=max_results,
                        headless=headless,
                        category=category,
                    ): platform
                    for platform in platforms
                }
                for future in as_completed(future_map):
                    platform = future_map[future]
                    try:
                        collected[platform] = future.result()
                    except Exception as exc:
                        collected[platform] = {
                            "source": platform,
                            "success": False,
                            "query": query,
                            "search_term": query,
                            "category": resolve_category(query, category),
                            "search_url": "",
                            "final_url": "",
                            "page_title": "",
                            "count": 0,
                            "items": [],
                            "error": normalize_text(str(exc)),
                            "note": "",
                            "html_snapshot": "",
                            "json_snapshot": "",
                            "elapsed_ms": 0.0,
                            "cache_hit": False,
                            "cached_age_seconds": 0.0,
                        }

            for platform in platforms:
                results[platform] = collected[platform]

        for result in results.values():
            total_items += result.get("count", 0)

        market_insights = build_market_insights(results)
        payload = {
            "success": True,
            "query": query,
            "category": resolve_category(query, category),
            "platforms": platforms,
            "total_items": total_items,
            "results": results,
            "market_insights": market_insights,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "parallel": len(platforms) > 1,
        }
        payload["json_snapshot"] = self.artifacts.save_json("combined", query, payload)
        return payload
