from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "Programita 2"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """Returns the source root or PyInstaller extraction root."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    return Path(__file__).resolve().parents[2]


def bundled_path(*parts: str) -> str:
    return str(project_root().joinpath(*parts))


def app_support_dir() -> Path:
    home = Path.home()
    return home / "Library" / "Application Support" / APP_NAME


def ensure_app_support_dir() -> Path:
    path = app_support_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_data_path(*parts: str) -> str:
    base = ensure_app_support_dir()
    full_path = base.joinpath(*parts)
    if parts and parts[-1] and "." not in Path(parts[-1]).name:
        full_path.mkdir(parents=True, exist_ok=True)
    return str(full_path)


def config_file_path() -> str:
    return str(ensure_app_support_dir() / "config.json")


def default_sections_dir() -> str:
    return user_data_path("sections")


def default_segments_dir() -> str:
    return user_data_path("segments")


def running_from_project_root() -> bool:
    try:
        return Path(os.getcwd()).resolve() == project_root()
    except Exception:
        return False
