from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT_DIR / "build"
PYINSTALLER_WORK_DIR = BUILD_DIR / "pyinstaller"
DIST_DIR = ROOT_DIR / "dist"
ICON_SCRIPT = ROOT_DIR / "tools" / "generate_app_icon.py"
ICON_PATH = ROOT_DIR / "assets" / "marketplace-search.ico"
ENTRYPOINT = ROOT_DIR / "main.py"
UI_FILE = ROOT_DIR / "marketplace_search" / "ui.html"
EXE_NAME = "Marketplace Search"


def run_command(command: list[str], description: str) -> None:
    print(f"[build] {description}...")
    subprocess.run(command, cwd=ROOT_DIR, check=True)


def ensure_icon() -> None:
    run_command([sys.executable, str(ICON_SCRIPT)], "Gerando icone do aplicativo")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Empacota o Marketplace Search para Windows."
    )
    parser.add_argument(
        "--mode",
        choices=["onefile", "onedir"],
        default="onefile",
        help="Formato do build. 'onedir' costuma ser mais estavel para distribuicao local.",
    )
    parser.add_argument(
        "--name",
        default=EXE_NAME,
        help="Nome do executavel gerado.",
    )
    return parser.parse_args(argv)


def build_executable(mode: str = "onefile", name: str = EXE_NAME) -> Path:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    PYINSTALLER_WORK_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    pyinstaller_mode_flag = "--onefile" if mode == "onefile" else "--onedir"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        pyinstaller_mode_flag,
        "--console",
        "--name",
        name,
        "--icon",
        str(ICON_PATH),
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(PYINSTALLER_WORK_DIR),
        "--specpath",
        str(BUILD_DIR),
        "--add-data",
        f"{UI_FILE};marketplace_search",
        "--collect-all",
        "fastapi",
        "--collect-all",
        "pydantic",
        "--collect-all",
        "requests",
        "--collect-all",
        "selenium",
        "--collect-all",
        "starlette",
        "--collect-all",
        "uvicorn",
        "--collect-data",
        "certifi",
        str(ENTRYPOINT),
    ]
    run_command(command, f"Empacotando executavel do Marketplace Search ({mode})")

    if mode == "onefile":
        return DIST_DIR / f"{name}.exe"

    return DIST_DIR / name / f"{name}.exe"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_icon()
    exe_path = build_executable(mode=args.mode, name=args.name)
    print(f"[build] Executavel pronto em: {exe_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
