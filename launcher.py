from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
VENV_DIR = ROOT_DIR / ".venv"
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"
STATE_DIR = ROOT_DIR / ".launcher"
REQUIREMENTS_STAMP = STATE_DIR / "requirements.sha256"
MAIN_FILE = ROOT_DIR / "main.py"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
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
    STATE_DIR.mkdir(exist_ok=True)
    requirements_hash = sha256_file(REQUIREMENTS_FILE)
    installed_hash = REQUIREMENTS_STAMP.read_text(encoding="utf-8").strip() if REQUIREMENTS_STAMP.exists() else ""
    if not force and installed_hash == requirements_hash:
        print("[launcher] Dependencias ja estao atualizadas.")
        return
    run_command(
        [str(venv_python()), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
        "Instalando dependencias",
    )
    REQUIREMENTS_STAMP.write_text(requirements_hash, encoding="utf-8")


def start_application() -> int:
    print("[launcher] Abrindo Marketplace Search...")
    return subprocess.call([str(venv_python()), str(MAIN_FILE)], cwd=ROOT_DIR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepara o ambiente local e inicia o Marketplace Search."
    )
    parser.add_argument(
        "--reinstall",
        action="store_true",
        help="Forca a reinstalacao das dependencias do requirements.txt.",
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="Prepara o ambiente e encerra sem abrir a aplicacao.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        created = ensure_virtualenv()
        if created:
            upgrade_pip()
        install_requirements(force=args.reinstall)
        if args.bootstrap_only:
            print("[launcher] Ambiente pronto.")
            return 0
        return start_application()
    except subprocess.CalledProcessError as error:
        print(f"[launcher] Falha ao executar: {' '.join(error.cmd)}")
        return error.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
