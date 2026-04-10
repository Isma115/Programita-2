from pathlib import Path
import sys

import webview


def main():
    html_path = Path(__file__).with_name("diagram_editor.html")
    html = html_path.read_text(encoding="utf-8")

    webview.create_window(
        "Editor de Diagramas",
        html=html,
        width=1720,
        height=980,
        min_size=(1280, 760),
        resizable=True,
        maximized=True,
        background_color="#0f141d",
        text_select=True,
        zoomable=True,
    )
    preferred_gui = "cocoa" if sys.platform == "darwin" else None
    webview.start(gui=preferred_gui, debug=False, private_mode=True)


if __name__ == "__main__":
    main()
