"""
Addon: Documentar Codigo
Solicita una funcionalidad por input y copia al portapapeles un prompt para
generar documentacion de flujo de codigo en Markdown.
"""

from tkinter import simpledialog
from src.logic.prompt_rules import ensure_file_path_comment_instruction


def _build_prompt(target_functionality: str) -> str:
    """Construye el prompt final para el agente de codigo."""
    return ensure_file_path_comment_instruction(
        "Actua como un agente de codigo senior.\n"
        "Tu tarea es crear un documento Markdown sobre esta funcionalidad:\n\n"
        f"FUNCIONALIDAD A DOCUMENTAR: {target_functionality}\n\n"
        "Objetivo:\n"
        "- Documentar el flujo real del codigo paso por paso, desde el evento inicial hasta el final del proceso.\n"
        "- Explicar cada paso en lenguaje no tecnico y tecnico.\n"
        "- Incluir los trozos de codigo exactos que participan en cada paso.\n\n"
        "Instrucciones obligatorias:\n"
        "1. Usa pasos numerados (1, 2, 3, ...).\n"
        "2. En cada paso incluye:\n"
        "   - Que ocurre (no tecnico).\n"
        "   - Detalle tecnico.\n"
        "   - Codigo exacto relevante en bloque Markdown.\n"
        "3. Cubre todo el recorrido: disparador inicial, validaciones, llamadas intermedias, efectos secundarios y cierre.\n"
        "4. Indica archivo y funcion de cada fragmento (y linea aproximada si se puede).\n"
        "5. No inventes informacion. Si algo no se puede verificar en el codigo, indicalo claramente.\n"
        "6. Escribe en espanol claro y directo.\n\n"
        "Formato de salida esperado:\n"
        "- Titulo del documento.\n"
        "- Resumen ejecutivo corto.\n"
        "- Flujo completo en pasos numerados.\n"
        "- Seccion final de observaciones/riesgos detectados.\n"
    )


def run(app, args):
    """
    Copia al portapapeles un prompt para documentar una funcionalidad.

    Uso:
    - documentar codigo
    - documentar codigo <descripcion de funcionalidad>
    """
    if args:
        target_functionality = " ".join(args).strip()
    else:
        target_functionality = simpledialog.askstring(
            "Documentar codigo",
            "Que funcionalidad quieres documentar?",
            parent=app.root if hasattr(app, "root") else None,
        )
        if target_functionality is None:
            return "Operacion cancelada."
        target_functionality = target_functionality.strip()

    if not target_functionality:
        return "Error: Debes indicar una funcionalidad a documentar."

    prompt_text = _build_prompt(target_functionality)

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
        f"'{target_functionality}'."
    )
