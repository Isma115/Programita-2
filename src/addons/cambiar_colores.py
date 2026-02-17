from src.ui.styles import Styles
import tkinter as tk
from tkinter import ttk

def run(app, args):
    """
    Changes the application colors.
    Usage: cambiar colores [rojo|azul|verde|defecto]
    """
    if not args:
        print("Uso: cambiar colores [color]")
        return "Error: Falta el argumento de color."

    color_name = args[0].lower()
    
    # Define palettes
    palettes = {
        "rojo": {
            "COLOR_ACCENT": "#ED4245",
            "COLOR_ACCENT_HOVER": "#c03537",
        },
        "azul": {
            "COLOR_ACCENT": "#1E90FF", # Dodger Blue
            "COLOR_ACCENT_HOVER": "#1873cc",
        },
        "verde": {
            "COLOR_ACCENT": "#57F287",
            "COLOR_ACCENT_HOVER": "#3ba55c",
        },
        "amarillo": {
            "COLOR_ACCENT": "#FEE75C",
            "COLOR_ACCENT_HOVER": "#dcb928",
        },
        "defecto": {
            "COLOR_ACCENT": "#5865F2",
            "COLOR_ACCENT_HOVER": "#4752c4",
        }
    }

    if color_name not in palettes:
        return f"Error: Color '{color_name}' no reconocido. Opciones: rojo, azul, verde, amarillo, defecto."

    # Apply colors
    scheme = palettes[color_name]
    Styles.COLOR_ACCENT = scheme["COLOR_ACCENT"]
    Styles.COLOR_ACCENT_HOVER = scheme["COLOR_ACCENT_HOVER"]
    
    # Save to Config
    if hasattr(app, 'controller') and hasattr(app.controller, 'config_manager'):
        app.controller.config_manager.set_theme_colors(
            Styles.COLOR_ACCENT, 
            Styles.COLOR_ACCENT_HOVER
        )
    
    # Re-configure styles
    Styles.configure_styles(app.root)
    
    # Force update of non-ttk widgets that use these colors
    # This is a basic traversal to update common widgets
    _update_widgets(app.root)

    return f"Colores cambiados a '{color_name}'."

def _update_widgets(widget):
    """Recursively updates widget colors."""
    try:
        # Update Canvas borders (checkboxes) - specific to our implementation
        if isinstance(widget, tk.Canvas):
            # If it's the checkbox canvas, we might need to redraw it, 
            # but usually it draws on click/state. Refreshing bg if it matches sidebar/main
            if widget.cget("bg") in [Styles.COLOR_BG_MAIN, Styles.COLOR_BG_SIDEBAR, "#2b2d31", "#1e1f22"]:
                 # This is tricky because we don't know which one it was originally.
                 # But our canvases are usually transparent or specific.
                 pass

        # Update Listbox (Section Lists)
        if isinstance(widget, tk.Listbox):
            widget.configure(
                bg=Styles.COLOR_INPUT_BG,
                fg=Styles.COLOR_INPUT_FG,
                selectbackground=Styles.COLOR_ACCENT,
                selectforeground="#ffffff"
            )

        # Update Text (Prompt, Editor)
        if isinstance(widget, tk.Text):
            widget.configure(
                bg=Styles.COLOR_INPUT_BG,
                fg=Styles.COLOR_INPUT_FG,
                insertbackground=Styles.COLOR_FG_TEXT if Styles.COLOR_FG_TEXT else "white"
            )
            
        # Specific fix for DocView Editor/Viewer toggles if they are custom
        # But generally they use ttk styles or are redrawn on toggle.

        # Recursively check children
        for child in widget.winfo_children():
            _update_widgets(child)
            
    except Exception as e:
        print(f"Error updating widget {widget}: {e}")
