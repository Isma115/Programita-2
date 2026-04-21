"""
Addon: Documentar Parte
Genera y copia al portapapeles un prompt para documentar una parte especifica
de una app/software en formato Markdown.
"""

from tkinter import simpledialog
from src.logic.prompt_rules import ensure_file_path_comment_instruction


def _build_prompt(target_part: str) -> str:
    """Construye el prompt final para el agente de codigo."""
    return ensure_file_path_comment_instruction(
        "Actua como un agente de codigo senior y genera un documento en Markdown "
        "detallado, claro y directo sobre la siguiente parte del sistema:\n\n"
        f"PARTE A DOCUMENTAR: {target_part}\n\n"
        "Objetivo del documento:\n"
        "- Al principio del documento md explicar de forma no técnica pero completa como funciona esta parte.\n"
        "- Incluir el flujo real de inicio a fin.\n"
        "- Incluir funcionalidades, reglas, entradas, salidas y dependencias.\n\n"
        "- No inventar: si falta informacion, indicarlo explicitamente.\n"
        "- Lenguaje claro, tecnico y directo.\n"
        "- Usar listas y subtitulos para escaneado rapido.\n"
        "- Priorizar precision sobre texto relleno.\n"
    )


def run(app, args):
    """
    Copia al portapapeles un prompt para documentar una parte concreta.

    Uso:
    - documentar parte
    - documentar parte <descripcion de la parte>
    """
    if args:
        target_part = " ".join(args).strip()
    else:
        target_part = simpledialog.askstring(
            "Documentar parte",
            "Que parte del software/pagina/app quieres documentar?",
            parent=app.root if hasattr(app, "root") else None,
        )
        if target_part is None:
            return "Operacion cancelada."
        target_part = target_part.strip()

    if not target_part:
        return "Error: Debes indicar la parte a documentar."

    prompt_text = _build_prompt(target_part)

    if hasattr(app, "controller") and hasattr(app.controller, "copy_to_clipboard"):
        copied = app.controller.copy_to_clipboard(prompt_text)
    else:
        try:
            app.root.clipboard_clear()
            app.root.clipboard_append(prompt_text)
            copied = True
        except Exception:
            copied = False

    if not copied:
        return "Error: No se pudo copiar el prompt al portapapeles."

    return (
        "Prompt de documentacion copiado al portapapeles para: "
        f"'{target_part}'."
    )
