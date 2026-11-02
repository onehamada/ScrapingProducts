from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from marketplace_search.settings import ensure_runtime_directories, get_settings


ROOT_DIR = Path(__file__).resolve().parent
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
VENV_DIR = ROOT_DIR / f".venv-py{PYTHON_VERSION}"
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"
PYPROJECT_FILE = ROOT_DIR / "pyproject.toml"
SETTINGS = ensure_runtime_directories(get_settings())
STATE_DIR = SETTINGS.launcher_state_dir
REQUIREMENTS_STAMP = STATE_DIR / f"requirements-py{PYTHON_VERSION}.sha256"
UPDATE_STATE_FILE = STATE_DIR / "update-state.json"
DEFAULT_UPDATE_REPO = "https://github.com/onehamada/ScrapingProducts"
DEFAULT_UPDATE_BRANCH = "main"
DEFAULT_UPDATE_CHECK_INTERVAL_SECONDS = 21600
PRESERVED_TOP_LEVEL_NAMES = {
    ".env",
    ".git",
    ".launcher",
    ".launcher-cache",
    ".selenium-profiles",
    ".venv",
    ".venv314",
    "artifacts",
    "build",
    "chrome-win64",
    "dist",
}


def sha256_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path).encode("utf-8"))
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(65536), b""):
                digest.update(chunk)
    return digest.hexdigest()


def current_python() -> str:
    return sys.executable


def venv_python() -> Path:
    if sys.platform.startswith("win"):
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run_command(command: list[str], description: str) -> None:
    print(f"[launcher] {description}...")
    subprocess.run(command, cwd=ROOT_DIR, check=True)


def env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"", "0", "false", "no", "off"}


def env_int(name: str, default: int, minimum: int = 0) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value.strip())
    except ValueError:
        return default
    return value if value >= minimum else default


def normalize_repo_slug(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""

    match = re.search(
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?/?$",
        raw,
        re.IGNORECASE,
    )
    if match:
        return f"{match.group('owner')}/{match.group('repo')}"

    match = re.fullmatch(r"(?P<owner>[^/]+)/(?P<repo>[^/.]+)", raw)
    if match:
        return f"{match.group('owner')}/{match.group('repo')}"

    return ""


def update_repo_slug() -> str:
    configured = os.getenv("MARKETPLACE_UPDATE_REPO", "").strip()
    slug = normalize_repo_slug(configured)
    if slug:
        return slug
    return normalize_repo_slug(DEFAULT_UPDATE_REPO)


def update_branch() -> str:
    return os.getenv("MARKETPLACE_UPDATE_BRANCH", DEFAULT_UPDATE_BRANCH).strip() or DEFAULT_UPDATE_BRANCH


def update_check_interval_seconds() -> int:
    return env_int(
        "MARKETPLACE_UPDATE_CHECK_INTERVAL_SECONDS",
        DEFAULT_UPDATE_CHECK_INTERVAL_SECONDS,
        minimum=0,
    )


def github_raw_url(repo_slug: str, branch: str, relative_path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo_slug}/{branch}/{relative_path}"


def github_archive_url(repo_slug: str, branch: str) -> str:
    return f"https://codeload.github.com/{repo_slug}/zip/refs/heads/{branch}"


def read_url_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"MarketplaceSearchLauncher/{SETTINGS.version}",
            "Accept": "text/plain,application/octet-stream;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def extract_version_from_pyproject(text: str) -> str:
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', text)
    return match.group(1).strip() if match else ""


def version_key(value: str) -> tuple[int, ...]:
    numbers = [int(part) for part in re.findall(r"\d+", value or "")]
    return tuple(numbers) if numbers else (0,)


def load_update_state() -> dict[str, object]:
    if not UPDATE_STATE_FILE.exists():
        return {}
    try:
        return json.loads(UPDATE_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_update_state(payload: dict[str, object]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    UPDATE_STATE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def should_preserve_top_level(path: Path) -> bool:
    if path.name in PRESERVED_TOP_LEVEL_NAMES:
        return True
    if path.name.startswith(".venv"):
        return True
    return False


def copy_update_tree(source_root: Path, destination_root: Path) -> None:
    for source in source_root.iterdir():
        if should_preserve_top_level(source):
            continue
        destination = destination_root / source.name
        if source.is_dir():
            shutil.copytree(
                source,
                destination,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def fetch_remote_version(repo_slug: str, branch: str) -> str:
    try:
        pyproject_text = read_url_text(github_raw_url(repo_slug, branch, "pyproject.toml"))
    except Exception:
        return ""
    return extract_version_from_pyproject(pyproject_text)


def fetch_remote_revision(repo_slug: str, branch: str) -> str:
    api_url = f"https://api.github.com/repos/{repo_slug}/commits/{branch}"
    request = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": f"MarketplaceSearchLauncher/{SETTINGS.version}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    revision = str(payload.get("sha", "")).strip()
    if not revision:
        raise RuntimeError("Nao foi possivel ler o commit remoto do GitHub.")
    return revision


def current_install_revision() -> str:
    git_dir = ROOT_DIR / ".git"
    if git_dir.exists():
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT_DIR,
                check=True,
                capture_output=True,
                text=True,
            )
            revision = result.stdout.strip()
            if revision:
                return revision
        except (OSError, subprocess.CalledProcessError):
            pass

    state = load_update_state()
    return str(state.get("installed_commit", "") or "").strip()


def download_and_apply_update(repo_slug: str, branch: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="marketplace-update-", dir=STATE_DIR) as temp_dir:
        temp_path = Path(temp_dir)
        archive_path = temp_path / "update.zip"
        request = urllib.request.Request(
            github_archive_url(repo_slug, branch),
            headers={"User-Agent": f"MarketplaceSearchLauncher/{SETTINGS.version}"},
        )
        with urllib.request.urlopen(request, timeout=60) as response, archive_path.open("wb") as output:
            shutil.copyfileobj(response, output)

        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(temp_path)

        extracted_roots = [path for path in temp_path.iterdir() if path.is_dir()]
        if not extracted_roots:
            raise RuntimeError("O pacote baixado nao trouxe arquivos validos para atualizar.")

        source_root = extracted_roots[0]
        copy_update_tree(source_root, ROOT_DIR)


def relaunch_command_args() -> list[str]:
    forwarded = [
        argument
        for argument in sys.argv[1:]
        if argument not in {"--auto-update", "--skip-update", "--update-only"}
    ]
    return [current_python(), str(ROOT_DIR / "launcher.py"), "--skip-update", *forwarded]


def maybe_self_update(args: argparse.Namespace) -> str | None:
    update_enabled = (
        args.update_only
        or (args.auto_update if args.auto_update is not None else env_bool("MARKETPLACE_AUTO_UPDATE", False))
    )
    if not update_enabled:
        return None

    repo_slug = update_repo_slug()
    if not repo_slug:
        message = "Repositorio de update invalido. Configure MARKETPLACE_UPDATE_REPO."
        if args.update_only:
            raise RuntimeError(message)
        print(f"[launcher] {message}")
        return None

    branch = update_branch()
    interval_seconds = update_check_interval_seconds()
    state = load_update_state()
    last_checked = float(state.get("checked_at", 0.0) or 0.0)
    now = time.time()

    if (
        not args.update_only
        and interval_seconds > 0
        and last_checked > 0
        and (now - last_checked) < interval_seconds
    ):
        return None

    print("[launcher] Verificando atualizacoes no GitHub...")
    try:
        remote_version = fetch_remote_version(repo_slug, branch)
        remote_revision = fetch_remote_revision(repo_slug, branch)
    except Exception as error:
        save_update_state(
            {
                "checked_at": now,
                "error": str(error),
                "repo": repo_slug,
                "branch": branch,
            }
        )
        if args.update_only:
            raise RuntimeError(f"Falha ao verificar atualizacoes: {error}") from error
        print(f"[launcher] Nao foi possivel verificar atualizacoes: {error}")
        return None

    state_payload: dict[str, object] = {
        "checked_at": now,
        "repo": repo_slug,
        "branch": branch,
        "local_version": SETTINGS.version,
        "remote_version": remote_version,
        "remote_revision": remote_revision,
    }

    local_revision = current_install_revision()
    has_newer_version = bool(remote_version) and version_key(remote_version) > version_key(SETTINGS.version)
    has_newer_revision = bool(remote_revision) and bool(local_revision) and remote_revision != local_revision

    if not has_newer_version and not has_newer_revision:
        save_update_state(state_payload)
        if args.update_only:
            print("[launcher] Esta maquina ja esta na versao mais recente.")
        return None

    if has_newer_version:
        print(f"[launcher] Atualizacao disponivel: {SETTINGS.version} -> {remote_version}")
    else:
        short_local = local_revision[:7] if local_revision else "desconhecido"
        print(
            "[launcher] Atualizacao disponivel pelo GitHub: "
            f"{short_local} -> {remote_revision[:7]}"
        )
    download_and_apply_update(repo_slug, branch)
    state_payload["updated_at"] = time.time()
    state_payload["updated_to"] = remote_version or SETTINGS.version
    state_payload["installed_commit"] = remote_revision
    save_update_state(state_payload)
    if remote_version:
        print(f"[launcher] Atualizacao aplicada para a versao {remote_version}.")
        return remote_version
    print(f"[launcher] Atualizacao aplicada para o commit {remote_revision[:7]}.")
    return remote_revision


def ensure_virtualenv() -> bool:
    python_path = venv_python()
    if python_path.exists():
        return False
    run_command(
        [current_python(), "-m", "venv", str(VENV_DIR)],
        "Criando ambiente virtual",
    )
    return True


def upgrade_pip() -> None:
    run_command(
        [str(venv_python()), "-m", "pip", "install", "--upgrade", "pip"],
        "Atualizando pip",
    )


def install_requirements(force: bool = False) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    requirements_hash = sha256_files([REQUIREMENTS_FILE, PYPROJECT_FILE])
    installed_hash = REQUIREMENTS_STAMP.read_text(encoding="utf-8").strip() if REQUIREMENTS_STAMP.exists() else ""
    if not force and installed_hash == requirements_hash:
        print("[launcher] Dependencias ja estao atualizadas.")
        return
    run_command(
        [str(venv_python()), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
        "Instalando dependencias",
    )
    REQUIREMENTS_STAMP.write_text(requirements_hash, encoding="utf-8")


def start_application(args: argparse.Namespace) -> int:
    print("[launcher] Abrindo Marketplace Search...")
    command = [str(venv_python()), "-m", "marketplace_search"]
    if args.host:
        command.extend(["--host", args.host])
    if args.port:
        command.extend(["--port", str(args.port)])
    if args.open_browser is not None:
        command.append("--open-browser" if args.open_browser else "--no-browser")
    if args.log_level:
        command.extend(["--log-level", args.log_level])
    return subprocess.call(command, cwd=ROOT_DIR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepara o ambiente local e inicia o Marketplace Search."
    )
    parser.add_argument(
        "--reinstall",
        action="store_true",
        help="Forca a reinstalacao das dependencias do projeto.",
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="Prepara o ambiente e encerra sem abrir a aplicacao.",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host para expor a API local.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Porta para expor a API local.",
    )
    browser_group = parser.add_mutually_exclusive_group()
    browser_group.add_argument(
        "--open-browser",
        dest="open_browser",
        action="store_true",
        default=None,
        help="Forca a abertura automatica do navegador.",
    )
    browser_group.add_argument(
        "--no-browser",
        dest="open_browser",
        action="store_false",
        help="Inicia sem abrir o navegador automaticamente.",
    )
    update_group = parser.add_mutually_exclusive_group()
    update_group.add_argument(
        "--auto-update",
        dest="auto_update",
        action="store_true",
        default=None,
        help="Verifica e aplica atualizacoes do GitHub antes de iniciar.",
    )
    update_group.add_argument(
        "--skip-update",
        dest="auto_update",
        action="store_false",
        help="Ignora a verificacao de atualizacoes nesta execucao.",
    )
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Baixa a versao mais recente do GitHub e encerra sem abrir o app.",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Nivel de log do servidor.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not (3, 11) <= sys.version_info[:2] < (3, 15):
        current_version = ".".join(str(part) for part in sys.version_info[:3])
        print(
            "[launcher] Python 3.11 a 3.14 e necessario. "
            f"Versao atual: {current_version}. Instale Python 3.13 e tente novamente."
        )
        return 1

    try:
        updated_version = maybe_self_update(args)
        if args.update_only:
            if updated_version is None:
                print("[launcher] Nenhuma atualizacao nova foi aplicada.")
            return 0
        if updated_version is not None:
            print("[launcher] Reiniciando launcher para carregar a nova versao...")
            return subprocess.call(relaunch_command_args(), cwd=ROOT_DIR)
        created = ensure_virtualenv()
        if created:
            upgrade_pip()
        install_requirements(force=args.reinstall)
        if args.bootstrap_only:
            print("[launcher] Ambiente pronto.")
            return 0
        return start_application(args)
    except subprocess.CalledProcessError as error:
        print(f"[launcher] Falha ao executar: {' '.join(error.cmd)}")
        return error.returncode or 1
    except RuntimeError as error:
        print(f"[launcher] {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
