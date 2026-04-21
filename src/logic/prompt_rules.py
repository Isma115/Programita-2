"""Helpers for enforcing shared prompt instructions."""

FILE_PATH_COMMENT_EXAMPLE = "Archivo: (ruta/al/archivo.ext)"

FILE_PATH_COMMENT_INSTRUCTION = (
    "Instruccion obligatoria sobre el codigo:\n"
    f'- En cada archivo o bloque de codigo que devuelvas, incluye dentro del propio codigo un comentario con el formato exacto "{FILE_PATH_COMMENT_EXAMPLE}", '
    "sustituyendo el ejemplo por la ruta real del archivo.\n"
)


def get_file_path_comment_inline_instruction():
    """Returns the inline instruction used inside code-return prompts."""
    return (
        "En cada archivo o bloque que devuelvas, incluye dentro del codigo un comentario "
        f'con el formato exacto "{FILE_PATH_COMMENT_EXAMPLE}", usando la ruta real del archivo.'
    )


def ensure_file_path_comment_instruction(prompt_text):
    """Appends the shared file path comment rule to a prompt when missing."""
    text = (prompt_text or "").rstrip()
    if FILE_PATH_COMMENT_EXAMPLE in text:
        return text
    if not text:
        return FILE_PATH_COMMENT_INSTRUCTION.rstrip()
    return f"{text}\n\n{FILE_PATH_COMMENT_INSTRUCTION.rstrip()}"
