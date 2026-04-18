import sys
import os

# Ensure the project root is in the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.app import Application

def main():
    """
    Entry point for Programita 2.
    """
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
