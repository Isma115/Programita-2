import sys
import os

# Ensure the project root is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def run_diagram_webview():
    from src.ui.popups.diagram_webview_app import main as diagram_webview_main
    diagram_webview_main()


from src.app import Application

def main():
    """
    Entry point for Programita 2.
    """
    if "--diagram-webview" in sys.argv:
        run_diagram_webview()
        return

    app = Application()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        # Stop the pynput listener BEFORE Python tears down the GIL so
        # pynput's CoreFoundation thread doesn't call PyEval_RestoreThread
        # on a NULL thread state (fatal crash on macOS).
        try:
            if hasattr(app, 'controller') and hasattr(app.controller, 'hotkey_listener'):
                app.controller.hotkey_listener.stop()
        except Exception:
            pass

if __name__ == "__main__":
    main()
