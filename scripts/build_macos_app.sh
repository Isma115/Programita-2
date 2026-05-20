#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="Programita 2"
APP_BUNDLE_ID="${APP_BUNDLE_ID:-com.programita2.desktop}"
VENV_DIR="$ROOT_DIR/.venv-build"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ICON_PNG="$ROOT_DIR/assets/icons/app_icon.png"
ICON_ICNS="$ROOT_DIR/assets/icons/app_icon.icns"
ICON_CONTENT_SCALE="${ICON_CONTENT_SCALE:-0.82}"
PIP_CACHE_DIR="$ROOT_DIR/.pip-cache"
PYINSTALLER_CONFIG_DIR="$ROOT_DIR/.pyinstaller"

echo "==> Root: $ROOT_DIR"
echo "==> Bundle ID: $APP_BUNDLE_ID"
echo "==> Creating build venv at: $VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
mkdir -p "$PIP_CACHE_DIR" "$PYINSTALLER_CONFIG_DIR"
export PIP_CACHE_DIR
export PYINSTALLER_CONFIG_DIR

echo "==> Installing dependencies"
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r "$ROOT_DIR/requirements.txt" pyinstaller

echo "==> Verifying macOS hotkey dependencies"
python - <<'PY'
import importlib
required_modules = ("Quartz", "HIServices", "ApplicationServices")
missing = []
for module_name in required_modules:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        missing.append(f"{module_name}: {exc}")

if missing:
    raise SystemExit(
        "Missing macOS hotkey dependencies in build environment:\n- "
        + "\n- ".join(missing)
    )
PY

if [[ ! -f "$ICON_PNG" ]]; then
  echo "Error: icon source not found at $ICON_PNG"
  exit 1
fi

echo "==> Preparing app icon (.icns) from app_icon.png"
python - "$ICON_PNG" "$ICON_ICNS" "$ICON_CONTENT_SCALE" <<'PY'
from PIL import Image
import sys

src, dst, scale_raw = sys.argv[1:4]
scale = max(0.10, min(1.00, float(scale_raw)))

img = Image.open(src).convert("RGBA")
side = max(img.size)
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas.alpha_composite(img, ((side - img.width) // 2, (side - img.height) // 2))

content_side = max(1, int(side * scale))
content = canvas.resize((content_side, content_side), Image.Resampling.LANCZOS)

out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
out.alpha_composite(content, ((side - content_side) // 2, (side - content_side) // 2))
out.save(
    dst,
    format="ICNS",
    sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)],
)
PY

echo "==> Cleaning previous artifacts"
rm -rf "$ROOT_DIR/build" "$ROOT_DIR/dist"

echo "==> Building macOS app bundle"
pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name "$APP_NAME" \
  --osx-bundle-identifier "$APP_BUNDLE_ID" \
  --icon "$ICON_ICNS" \
  --paths "$ROOT_DIR" \
  --collect-submodules src.addons \
  --collect-submodules tkinterweb \
  --hidden-import Quartz \
  --hidden-import HIServices \
  --hidden-import ApplicationServices \
  --hidden-import CoreFoundation \
  --hidden-import tkinterweb.bindings \
  --add-data "$ROOT_DIR/assets:assets" \
  --add-data "$ROOT_DIR/ias_disponibles.txt:." \
  --add-data "$ROOT_DIR/sections:sections" \
  --add-data "$ROOT_DIR/segments:segments" \
  --add-data "$ROOT_DIR/src/logic/js_ast_structures.js:src/logic" \
  --add-data "$ROOT_DIR/src/ui/popups/diagram_editor.html:src/ui/popups" \
  "$ROOT_DIR/main.py"

echo "==> Creating distributable zip"
ditto -c -k --sequesterRsrc --keepParent \
  "$ROOT_DIR/dist/$APP_NAME.app" \
  "$ROOT_DIR/dist/$APP_NAME-macOS.zip"

echo "Build complete:"
echo "  App: $ROOT_DIR/dist/$APP_NAME.app"
echo "  Zip: $ROOT_DIR/dist/$APP_NAME-macOS.zip"
