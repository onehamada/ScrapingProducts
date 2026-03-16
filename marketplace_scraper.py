from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.chrome.options import Options


ROOT_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
ARTIFACTS_HTML_DIR = ARTIFACTS_DIR / "html"
ARTIFACTS_JSON_DIR = ARTIFACTS_DIR / "json"
PROFILE_ROOT = ROOT_DIR / ".selenium-profiles"
LOCAL_CHROME = ROOT_DIR / "chrome-win64" / "chrome.exe"
FACEBOOK_DEFAULT_REGION_SLUG = "saopaulo"
PROFILE_LOCK_FILES = (
    "SingletonCookie",
    "SingletonLock",
    "SingletonSocket",
    "lockfile",
)

R_CURRENCY = re.compile(r"R\$\s*[\d\.\,]+")
R_WHITESPACE = re.compile(r"\s+")
R_TOKEN = re.compile(r"[a-z0-9]+")
R_MEMORY_SIZE = re.compile(r"\b\d{1,3}\s*gb\b")
R_XEON_MODEL = re.compile(r"\bxeon\s*(e[357])?\s*[- ]?(\d{4})\s*(v\d+)?\b")
R_XEON_MODEL_FAMILY = re.compile(r"\b(e[357])\s*[- ]?(\d{4})\s*(v\d+)?\b")
R_INTEL_CORE_MODEL = re.compile(r"\b(?:core\s*)?i[3579]\s*[- ]?\d{3,5}[a-z]{0,2}\b")
R_RYZEN_MODEL = re.compile(r"\bryzen\s*(?:[3579]\s*)?\d{3,5}[a-z]{0,3}\b")
R_EPYC_MODEL = re.compile(r"\bepyc\s*\d{3,4}\b")

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
    "gabinete",
    "all in one",
    "cpu ",
    " cpu",
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

CATEGORY_CHOICES = (
    "auto",
    "placa-de-video",
    "notebook",
    "pc-completo",
    "processador",
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
}

SEARCH_CACHE_TTL_SECONDS = 120
SEARCH_CACHE_MAX_ENTRIES = 96
SEARCH_FALLBACK_MAX_ATTEMPTS = 3


def repair_mojibake(value: str) -> str:
    text = value or ""
    if not text or not any(marker in text for marker in ("Ã", "Â", "â€", "â€™", "â€œ", "â€")):
        return text
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    return repaired


def normalize_text(value: str) -> str:
    return R_WHITESPACE.sub(" ", repair_mojibake(value or "")).strip()


def normalize_match_text(value: str) -> str:
    ascii_text = (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return normalize_text(re.sub(r"[^a-z0-9]+", " ", ascii_text))


def compact_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_match_text(value))


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


def parse_price_value(text: str) -> float | None:
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


def match_tokens(value: str) -> list[str]:
    expanded = normalize_match_text(value)
    expanded = re.sub(r"([a-z])([0-9])", r"\1 \2", expanded)
    expanded = re.sub(r"([0-9])([a-z])", r"\1 \2", expanded)
    tokens = []
    for token in R_TOKEN.findall(expanded):
        if token in STOPWORDS:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def query_tokens(query: str) -> list[str]:
    return [token for token in match_tokens(query) if token not in QUERY_NOISE_TOKENS]


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
    if not is_processor_query(query):
        return items

    return sorted(
        items,
        key=lambda item: (
            item.price_value is None,
            item.price_value if item.price_value is not None else float("inf"),
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
    return R_MEMORY_SIZE.search(normalized) is not None or any(
        term in normalized for term in ("ram", "memoria", "ddr3", "ddr4", "ddr5")
    )


def has_storage_facet(value: str) -> bool:
    normalized = normalize_match_text(value)
    return any(term in normalized for term in ("nvme", "ssd", "m 2", "m2", "hd "))


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
    candidates = [normalize_text(query)]

    if resolved_category == "placa-de-video":
        gpu_base_query = strip_query_terms(query, GPU_SEARCH_NOISE_TERMS)
        candidates.append(gpu_base_query)
        candidates.append(strip_memory_size_terms(gpu_base_query))
        candidates.append(build_gpu_core_query(gpu_base_query))

    if resolved_category == "processador":
        candidates.append(strip_query_terms(query, PROCESSOR_SEARCH_NOISE_TERMS))
        if is_xeon_query(query):
            candidates.append(build_xeon_bundle_search_query(query))
            candidates.append(build_xeon_search_query(query))

    return dedupe_terms(candidates)[:SEARCH_FALLBACK_MAX_ATTEMPTS]


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


def title_contains_query(query: str, title: str) -> bool:
    title_match = normalize_match_text(title)
    title_compact = compact_text(title)
    title_tokens = set(match_tokens(title))
    tokens = query_tokens(query)
    xeon_query = is_xeon_query(query)
    query_xeon_signature = extract_xeon_signature(query)

    if not tokens:
        return True

    if is_xeon_bundle_query(query):
        return has_xeon_bundle_query_match(query, title)

    if xeon_query and query_xeon_signature:
        return has_xeon_model_match(query, title)

    compact_query = "".join(tokens)
    if compact_query and compact_query in title_compact:
        return True

    return all(
        token in title_tokens or token in title_match or token in title_compact
        for token in tokens
    )


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
    if any(term in query_match for term in NOTEBOOK_TERMS):
        return "notebook"
    if any(term in query_match for term in PC_TERMS):
        return "pc-completo"
    if is_processor_query(query):
        return "processador"
    if any(term in query_match for term in GPU_QUERY_TERMS):
        return "placa-de-video"
    return "auto"


def evaluate_title_reason(query: str, title: str, resolved_category: str = "auto") -> str:
    title_match = normalize_match_text(title)
    query_match = normalize_match_text(query)
    title_tokens = set(match_tokens(title))
    query_token_set = set(match_tokens(query))
    gpu_query = any(term in query_match for term in GPU_QUERY_TERMS)
    xeon_query = is_xeon_query(query)
    processor_bundle_query = is_processor_bundle_query(query)

    if not title_contains_query(query, title):
        return "query_mismatch"

    if any(term in title_match for term in TITLE_BLOCK_TERMS) or has_untested_terms(title):
        return "blocked_term"

    if xeon_query and has_xeon_bundle_mismatch(query, title):
        return "bundle_term"

    if is_processor_query(query) and has_processor_bundle_mismatch(query, title):
        return "bundle_term"

    if has_server_oem_mismatch(query, title):
        return "bundle_term"

    if any(term in title_match and term not in query_match for term in BUNDLE_TERMS):
        return "bundle_term"

    if (resolved_category == "placa-de-video" or gpu_query) and has_gpu_variant_mismatch(query, title):
        return "variant_mismatch"

    if resolved_category == "placa-de-video":
        if has_any_match_term(title_match, title_tokens, NOTEBOOK_TERMS):
            return "category_mismatch"
        if any(
            has_match_term(title_match, title_tokens, term)
            and not has_match_term(query_match, query_token_set, term)
            for term in PC_TERMS
        ):
            return "category_mismatch"
        if any(
            has_match_term(title_match, title_tokens, term)
            and not has_match_term(query_match, query_token_set, term)
            for term in SYSTEM_SPEC_TERMS
        ):
            return "category_mismatch"
        if any(
            has_match_term(title_match, title_tokens, term)
            and not has_match_term(query_match, query_token_set, term)
            for term in GPU_ACCESSORY_TERMS
        ):
            return "category_mismatch"
    elif resolved_category == "notebook":
        if not has_any_match_term(title_match, title_tokens, NOTEBOOK_TERMS):
            return "category_mismatch"
    elif resolved_category == "pc-completo":
        if not has_any_match_term(title_match, title_tokens, PC_TERMS):
            return "category_mismatch"
    elif resolved_category == "processador":
        if any(
            has_match_term(title_match, title_tokens, term)
            and not has_match_term(query_match, query_token_set, term)
            for term in NOTEBOOK_TERMS
        ):
            return "category_mismatch"
        if any(
            has_match_term(title_match, title_tokens, term)
            and not has_match_term(query_match, query_token_set, term)
            for term in PC_TERMS
        ):
            return "category_mismatch"
        if (
            not processor_bundle_query
            and any(
                has_match_term(title_match, title_tokens, term)
                and not has_match_term(query_match, query_token_set, term)
                for term in PROCESSOR_BUNDLE_TERMS
            )
        ):
            return "bundle_term"
    elif gpu_query:
        if any(
            has_match_term(title_match, title_tokens, term)
            and not has_match_term(query_match, query_token_set, term)
            for term in SYSTEM_SPEC_TERMS
        ):
            return "bundle_term"

    return ""


def quartiles(values: list[float]) -> tuple[float, float]:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    lower = ordered[:midpoint]
    upper = ordered[midpoint:] if len(ordered) % 2 == 0 else ordered[midpoint + 1 :]
    return median(lower), median(upper)


def build_price_stats(items: list["Listing"]) -> dict[str, Any]:
    priced_items = [item for item in items if item.price_value is not None]
    values = [item.price_value for item in priced_items if item.price_value is not None]

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
        upper = min(iqr_upper, med * 1.80)
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


def extract_image(node: Any) -> str:
    image = node.select_one("img")
    if not image:
        return ""
    for attr in ("src", "data-src", "data-lazy", "data-srcset"):
        value = image.get(attr)
        if value:
            return value
    return ""


@dataclass
class Listing:
    source: str
    title: str
    price: str = ""
    price_value: float | None = None
    url: str = ""
    location: str = ""
    posted_at: str = ""
    installment: str = ""
    shipping: str = ""
    image: str = ""
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BrowserSession:
    driver: webdriver.Chrome
    lock: threading.Lock


@dataclass
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

    def save_html(self, platform: str, query: str, html: str) -> str:
        path = ARTIFACTS_HTML_DIR / self._filename(platform, query, "html")
        path.write_text(html, encoding="utf-8")
        return f"/artifacts/html/{path.name}"

    def save_json(self, platform: str, query: str, payload: dict[str, Any]) -> str:
        path = ARTIFACTS_JSON_DIR / self._filename(platform, query, "json")
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return f"/artifacts/json/{path.name}"


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
            payload = copy.deepcopy(entry.payload)

        payload["cache_hit"] = True
        payload["cached_age_seconds"] = round(now - entry.created_at, 1)
        payload["elapsed_ms"] = 0.0
        return payload

    def set(self, key: tuple[str, str, str, int, bool], payload: dict[str, Any]) -> None:
        stored = copy.deepcopy(payload)
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

    def _profile_dir(self, profile_name: str) -> Path:
        return PROFILE_ROOT / profile_name

    def _preferred_binaries(self) -> list[Path | None]:
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
        attempts: list[tuple[Path | None, bool]] = []
        for binary in self._preferred_binaries():
            attempts.append((binary, False))
            attempts.append((binary, True))

        last_error: Exception | None = None

        for chrome_binary, safe_mode in attempts:
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
                return self._configure_driver(driver)
            except (SessionNotCreatedException, WebDriverException) as exc:
                last_error = exc
                if not self._is_startup_crash(exc):
                    raise
                if persistent_profile:
                    self._cleanup_persistent_profile(profile_name)
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

    def filter_items(
        self,
        query: str,
        items: list[Listing],
        max_results: int,
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
            if reason:
                discarded[reason] += 1
                continue
            approved.append(item)

        approved = sort_items_for_query(query, approved)
        stats = build_price_stats(approved)
        stats["resolved_category"] = resolved_category
        stats["scanned_items"] = len(items)
        stats["matched_items"] = len(approved)
        stats["discarded_titles"] = sum(discarded.values())
        stats["discarded_reasons"] = discarded

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
        message = normalize_match_text(str(exc))
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
        return normalize_text(str(exc))

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

            html_snapshot = self.artifacts.save_html(self.source, query, page_html)

            if error:
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
                payload["json_snapshot"] = self.artifacts.save_json(self.source, query, payload)
                return payload

            raw_limit = max(30, max_results * 4)
            raw_items = self.parse_items(page_html, raw_limit)
            items, stats = self.filter_items(display_query, raw_items, max_results, category)
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
                    f"{stats['discarded_reasons']['category_mismatch']} descartados por nao baterem com a categoria aplicada"
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
                "html_snapshot": html_snapshot,
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
            payload["json_snapshot"] = self.artifacts.save_json(self.source, query, payload)
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
        soup = BeautifulSoup(page_html, "html.parser")
        cards = soup.select("li.ui-search-layout__item")
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

    def parse_items(self, page_html: str, max_results: int) -> list[Listing]:
        soup = BeautifulSoup(page_html, "html.parser")
        cards = soup.select("section.olx-adcard")
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
        soup = BeautifulSoup(page_html, "html.parser")
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
        soup = BeautifulSoup(page_html, "html.parser")
        cards = soup.select("div.product-item")
        items: list[Listing] = []
        seen_urls: set[str] = set()

        for card in cards:
            title_link = card.select_one("a.product-item__name")
            if not title_link:
                continue

            title = normalize_text(title_link.get("title") or title_link.get_text(" ", strip=True))
            url = title_link.get("href", "").strip()
            if not title or not url or url in seen_urls:
                continue

            price = first_matching_text(card.select("div.product-item__new-price"), R_CURRENCY)
            installment = first_matching_text(card.select("div.product-item__juros"))
            old_price = first_matching_text(card.select("div.product-item__old-price"), R_CURRENCY)
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


class FacebookMarketplaceScraper(BaseMarketplaceScraper):
    source = "facebook"
    profile_name = "facebook"
    persistent_profile = True
    open_wait_seconds = 2.1
    login_wait_seconds = 180
    login_poll_seconds = 2

    def build_search_url(self, query: str) -> str:
        return (
            "https://www.facebook.com/marketplace/"
            f"{FACEBOOK_DEFAULT_REGION_SLUG}/search/?query={quote_plus(query)}"
        )

    def _has_marketplace_surface(self, page_html: str) -> bool:
        lowered = page_html.lower()
        return (
            "resultados da pesquisa" in lowered
            or "nenhum classificado encontrado" in lowered
            or "pesquisar no marketplace" in lowered
            or 'aria-label="coleção de itens do marketplace"' in lowered
        )

    def _needs_login(self, page_html: str, current_url: str) -> bool:
        lowered_url = current_url.lower()
        if "/login" in lowered_url:
            return True
        if "/marketplace/" in lowered_url and self._has_marketplace_surface(page_html):
            return False

        soup = BeautifulSoup(page_html, "html.parser")
        return (
            soup.select_one('form input[name="email"]') is not None
            or soup.select_one('form input#email') is not None
        )

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
                "perfil salvo em .selenium-profiles/facebook para autenticar manualmente."
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

            return page_title, page_html, current_url

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
            result = copy.deepcopy(attempts[0])
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
            result = copy.deepcopy(successful[0])
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
        merged_items: dict[str, Listing] = {}

        for attempt in successful:
            for raw_item in attempt.get("items", []):
                item = Listing(**raw_item)
                key = item.url.strip() or f"{compact_text(item.title)}|{item.price}|{normalize_match_text(item.location)}"
                existing = merged_items.get(key)
                if existing is None:
                    merged_items[key] = item
                    continue

                if existing.price_value is None and item.price_value is not None:
                    merged_items[key] = item
                    continue

                if (
                    existing.price_value is not None
                    and item.price_value is not None
                    and item.price_value < existing.price_value
                ):
                    merged_items[key] = item
                    continue

                if len(item.title) < len(existing.title):
                    merged_items[key] = item

        items = sort_items_for_query(query, list(merged_items.values()))[:max_results]
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

        merged = copy.deepcopy(best)
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
        merged.pop("json_snapshot", None)
        merged["json_snapshot"] = self.artifacts.save_json(merged["source"], query, merged)
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
        target_count = min(max_results, 3 if resolved_category == "processador" else 2)

        for candidate in search_candidates:
            result = self._search_platform_once(
                platform=platform,
                query=candidate,
                match_query=query,
                max_results=max_results,
                headless=headless,
                category=category,
            )
            attempts.append(result)
            if result.get("success") and result.get("count", 0) >= target_count:
                break

        payload = self._merge_platform_results(
            query=query,
            category=category,
            max_results=max_results,
            attempts=attempts,
        )
        payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
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

        payload = {
            "success": True,
            "query": query,
            "category": resolve_category(query, category),
            "platforms": platforms,
            "total_items": total_items,
            "results": results,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "parallel": len(platforms) > 1,
        }
        payload["json_snapshot"] = self.artifacts.save_json("combined", query, payload)
        return payload
