import os
import subprocess
import sys

try:
    from AppKit import NSWorkspace
except Exception:
    NSWorkspace = None


KNOWN_EDITOR_BUNDLE_IDS = {
    "com.microsoft.vscode",
    "com.microsoft.vscodeinsiders",
    "com.vscodium",
    "com.sublimetext.4",
    "com.sublimetext.3",
    "com.macromates.textmate",
    "com.barebones.bbedit",
    "com.panic.nova",
    "com.github.zed",
    "com.jetbrains.fleet",
    "com.jetbrains.intellij",
    "com.jetbrains.pycharm",
    "com.jetbrains.webstorm",
    "com.jetbrains.phpstorm",
    "com.jetbrains.goland",
    "com.jetbrains.clion",
    "com.jetbrains.rider",
    "com.jetbrains.rubymine",
    "com.jetbrains.datagrip",
    "com.jetbrains.aqua",
}

EDITOR_NAME_KEYWORDS = (
    "antigravity",
    "bbedit",
    "codium",
    "cursor",
    "fleet",
    "goland",
    "intellij",
    "nova",
    "phpstorm",
    "pycharm",
    "rider",
    "rubymine",
    "sublime",
    "textmate",
    "vscodium",
    "visual studio code",
    "webstorm",
    "windsurf",
    "zed",
)

EXCLUDED_NAME_KEYWORDS = (
    "codex",
    "helper",
    "openai",
    "service",
    "crashpad",
    "reporter",
)

EDITOR_PRIORITY_RULES = (
    ("visual_studio_code", 10, ("com.microsoft.vscode", "com.microsoft.vscodeinsiders"), ("visual studio code", "code - insiders")),
    ("intellij_idea", 20, ("com.jetbrains.intellij",), ("intellij", "intellij idea")),
    ("pycharm", 30, ("com.jetbrains.pycharm",), ("pycharm",)),
    ("cursor", 40, tuple(), ("cursor",)),
    ("webstorm", 50, ("com.jetbrains.webstorm",), ("webstorm",)),
    ("goland", 60, ("com.jetbrains.goland",), ("goland",)),
    ("phpstorm", 70, ("com.jetbrains.phpstorm",), ("phpstorm",)),
    ("rider", 80, ("com.jetbrains.rider",), ("rider",)),
    ("clion", 90, ("com.jetbrains.clion",), ("clion",)),
    ("rubymine", 100, ("com.jetbrains.rubymine",), ("rubymine",)),
    ("datagrip", 110, ("com.jetbrains.datagrip",), ("datagrip",)),
    ("fleet", 120, ("com.jetbrains.fleet",), ("fleet",)),
    ("windsurf", 130, tuple(), ("windsurf",)),
    ("zed", 140, ("com.github.zed",), ("zed",)),
    ("nova", 150, ("com.panic.nova",), ("nova",)),
    ("sublime_text", 160, ("com.sublimetext.4", "com.sublimetext.3"), ("sublime", "sublime text")),
    ("textmate", 170, ("com.macromates.textmate",), ("textmate",)),
    ("bbedit", 180, ("com.barebones.bbedit",), ("bbedit",)),
    ("vscodium", 190, ("com.vscodium",), ("vscodium", "codium")),
    ("antigravity", 200, tuple(), ("antigravity",)),
    ("aqua", 210, ("com.jetbrains.aqua",), ("aqua",)),
)


def _normalize_text(value):
    return str(value or "").strip().lower()


def _is_supported_editor_app(app):
    app_name = _normalize_text(app.localizedName())
    bundle_id = _normalize_text(app.bundleIdentifier())

    if not app_name:
        return False
    if any(token in app_name for token in EXCLUDED_NAME_KEYWORDS):
        return False
    if any(token in bundle_id for token in EXCLUDED_NAME_KEYWORDS):
        return False
    if bundle_id in KNOWN_EDITOR_BUNDLE_IDS:
        return True
    if any(keyword in app_name for keyword in EDITOR_NAME_KEYWORDS):
        return True
    return any(keyword in bundle_id for keyword in EDITOR_NAME_KEYWORDS)


def _get_editor_priority(app_name, bundle_id):
    normalized_name = _normalize_text(app_name)
    normalized_bundle_id = _normalize_text(bundle_id)

    for _editor_key, priority, bundle_ids, keywords in EDITOR_PRIORITY_RULES:
        if normalized_bundle_id in bundle_ids:
            return priority
        if any(keyword in normalized_name for keyword in keywords):
            return priority
        if any(keyword in normalized_bundle_id for keyword in keywords):
            return priority
    return 10 ** 6


def get_running_editor_candidates():
    """Returns running GUI editors that can receive a file-open request."""
    if NSWorkspace is None:
        return []

    workspace = NSWorkspace.sharedWorkspace()
    candidates = []
    seen_keys = set()

    for app in workspace.runningApplications() or []:
        if not _is_supported_editor_app(app):
            continue

        bundle_id = str(app.bundleIdentifier() or "").strip()
        app_url = app.bundleURL()
        app_path = str(app_url.path()) if app_url else ""
        app_name = str(app.localizedName() or "").strip()
        key = (bundle_id.lower(), app_path.lower(), app_name.lower())

        if key in seen_keys:
            continue
        seen_keys.add(key)

        candidates.append({
            "name": app_name,
            "bundle_id": bundle_id,
            "path": app_path,
            "is_active": bool(app.isActive()),
            "is_hidden": bool(app.isHidden()),
            "priority": _get_editor_priority(app_name, bundle_id),
        })

    return candidates


def open_file_in_running_editor(file_path):
    """
    Opens a file in the best compatible editor app currently running.

    Returns:
        tuple[bool, str]: success flag and status/error message.
    """
    normalized_path = os.path.abspath(str(file_path or ""))
    if not normalized_path or not os.path.isfile(normalized_path):
        return False, "El archivo no existe o no se pudo resolver."

    candidates = get_running_editor_candidates()
    if not candidates:
        return False, "No hay ningún editor compatible abierto."

    chosen = sorted(
        candidates,
        key=lambda item: (
            int(item.get("priority", 10 ** 6)),
            0 if item.get("is_active") else 1,
            0 if not item.get("is_hidden") else 1,
            (item.get("name") or "").lower(),
        )
    )[0]

    commands = []
    bundle_id = chosen.get("bundle_id", "").strip()
    app_path = chosen.get("path", "").strip()
    app_name = chosen.get("name", "").strip()

    if bundle_id:
        commands.append(["open", "-b", bundle_id, normalized_path])
    if app_path:
        commands.append(["open", "-a", app_path, normalized_path])
    elif app_name:
        commands.append(["open", "-a", app_name, normalized_path])

    last_error = "No se pudo lanzar el editor."
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False
            )
        except Exception as exc:
            last_error = str(exc)
            continue

        if completed.returncode == 0:
            return True, f"Archivo abierto en {chosen.get('name') or 'el editor'}."

        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        last_error = stderr or stdout or last_error

    return False, last_error


def reveal_file_in_system_explorer(file_path):
    """
    Reveals a file in the user's system file explorer.

    Returns:
        tuple[bool, str]: success flag and status/error message.
    """
    normalized_path = os.path.abspath(str(file_path or ""))
    if not normalized_path or not os.path.exists(normalized_path):
        return False, "El archivo no existe o no se pudo resolver."

    is_directory = os.path.isdir(normalized_path)

    if sys.platform == "darwin":
        command = ["open", normalized_path] if is_directory else ["open", "-R", normalized_path]
    elif os.name == "nt":
        command = ["explorer", normalized_path] if is_directory else ["explorer", "/select,", normalized_path]
    else:
        target_dir = normalized_path if is_directory else os.path.dirname(normalized_path)
        if not target_dir or not os.path.isdir(target_dir):
            return False, "No se pudo resolver la carpeta contenedora del archivo."
        command = ["xdg-open", target_dir]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return False, str(exc)

    if completed.returncode == 0:
        return True, "Archivo mostrado en el explorador del sistema."

    stderr = (completed.stderr or "").strip()
    stdout = (completed.stdout or "").strip()
    return False, stderr or stdout or "No se pudo abrir el explorador de archivos."
