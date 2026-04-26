import configparser
import json
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from functools import lru_cache

try:
    import tomllib
except Exception:
    tomllib = None

try:
    import yaml
except Exception:
    yaml = None

from src.logic.project_manager import ProjectManager


SUPPORTED_SYNTAX_EXTENSIONS = frozenset(ProjectManager.CODE_EXTENSIONS)
SUPPORTED_SYNTAX_FILENAMES = frozenset(ProjectManager.CODE_FILENAMES)
MARKUP_TARGETS = frozenset(ProjectManager.MARKUP_EXTENSIONS)
BRACE_STYLE_TARGETS = frozenset(ProjectManager.BRACE_STYLE_EXTENSIONS)
END_STYLE_TARGETS = frozenset(ProjectManager.END_STYLE_EXTENSIONS)

DOCKERFILE_FILENAMES = {"Dockerfile", "Containerfile"}
RUBY_DSL_FILENAMES = {"Gemfile", "Rakefile", "Podfile", "Vagrantfile", "Brewfile"}
MAKE_FILENAMES = {"Makefile"}
PROCFILE_FILENAMES = {"Procfile"}
CMAKE_FILENAMES = {"CMakeLists.txt"}

LINE_COMMENT_TARGETS = {
    ".py", ".pyw", ".rb", ".toml", ".yml", ".yaml", ".ini", ".cfg", ".conf",
    ".properties", ".sh", ".bash", ".zsh", ".fish", ".dockerignore", ".editorconfig",
    ".pl", ".pm", ".r", ".jl", ".dart", ".ex", ".exs", ".erl", ".hrl",
}
C_STYLE_COMMENT_TARGETS = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx",
    ".cs", ".go", ".rs", ".zig", ".java", ".kt", ".kts", ".scala", ".groovy",
    ".gradle", ".swift", ".m", ".mm", ".php", ".phtml", ".js", ".mjs", ".cjs",
    ".jsx", ".ts", ".tsx", ".css", ".scss", ".sass", ".less", ".graphql", ".gql",
    ".proto", ".json", ".jsonc",
}
DASH_COMMENT_TARGETS = {".sql", ".lua"}
HTML_COMMENT_TARGETS = MARKUP_TARGETS | {".html", ".htm", ".xhtml", ".xml", ".xsd", ".xsl", ".wsdl"}
BACKTICK_STRING_TARGETS = {
    ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx",
    ".sh", ".bash", ".zsh", ".fish",
    ".vue", ".svelte", ".astro", ".ejs", ".hbs", ".handlebars",
    ".mustache", ".njk", ".twig", ".jinja", ".jinja2", ".tpl",
}
XML_TARGETS = {".xml", ".xsd", ".xsl", ".wsdl", ".svg"}
HTML_LIKE_TARGETS = MARKUP_TARGETS | {".html", ".htm"}

DOCKERFILE_INSTRUCTIONS = {
    "FROM", "RUN", "CMD", "LABEL", "MAINTAINER", "EXPOSE", "ENV", "ADD", "COPY",
    "ENTRYPOINT", "VOLUME", "USER", "WORKDIR", "ARG", "ONBUILD", "STOPSIGNAL",
    "HEALTHCHECK", "SHELL",
}
HTML_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
SYNTAX_LIKE_MESSAGE_RE = re.compile(
    r"(?i)\b("
    r"syntax|parse|expected|unexpected|unterminated|unmatched|"
    r"missing|illegal start|invalid character|invalid syntax|"
    r"reached end of file|missing separator|can't find string terminator|"
    r"no terminator|delimiter|initializer|statement expected|expression expected"
    r")\b"
)


def _normalize_text(text):
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _build_validation_result(
    *,
    supported,
    ok,
    message,
    line=None,
    column=None,
    end_line=None,
    end_column=None,
    engine=None,
):
    return {
        "supported": supported,
        "ok": ok,
        "message": message,
        "line": line,
        "column": column,
        "end_line": end_line,
        "end_column": end_column,
        "engine": engine,
    }


def _unknown_target_result(file_path):
    return _build_validation_result(
        supported=False,
        ok=True,
        message=f"Validacion no disponible para {os.path.basename(file_path or '') or 'este fichero'}",
        engine="none",
    )


def _target_from_path(file_path):
    basename = os.path.basename(file_path or "")
    basename_lower = basename.lower()
    extension = os.path.splitext(basename)[1].lower()

    if basename in SUPPORTED_SYNTAX_FILENAMES:
        return basename
    if basename_lower in SUPPORTED_SYNTAX_EXTENSIONS:
        return basename_lower
    if extension in SUPPORTED_SYNTAX_EXTENSIONS:
        return extension
    return None


def _language_label(target):
    labels = {
        ".py": "Python",
        ".pyw": "Python",
        ".json": "JSON",
        ".jsonc": "JSONC",
        ".toml": "TOML",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".xml": "XML",
        ".xsd": "XML",
        ".xsl": "XML",
        ".wsdl": "XML",
        ".svg": "SVG",
        ".ini": "INI",
        ".properties": "Properties",
        ".js": "JavaScript",
        ".mjs": "JavaScript",
        ".cjs": "JavaScript",
        ".ts": "TypeScript",
        ".jsx": "JSX",
        ".tsx": "TSX",
        ".sh": "Shell",
        ".bash": "Bash",
        ".zsh": "Zsh",
        ".fish": "Fish",
        ".rb": "Ruby",
        ".pl": "Perl",
        ".pm": "Perl",
        ".php": "PHP",
        ".java": "Java",
        ".kt": "Kotlin",
        ".kts": "Kotlin",
        ".scala": "Scala",
        ".groovy": "Groovy",
        ".gradle": "Gradle",
        ".c": "C",
        ".cc": "C++",
        ".cpp": "C++",
        ".cxx": "C++",
        ".h": "C/C++ Header",
        ".hh": "C++ Header",
        ".hpp": "C++ Header",
        ".hxx": "C++ Header",
        ".cs": "C#",
        ".vb": "Visual Basic",
        ".fs": "F#",
        ".fsx": "F#",
        ".go": "Go",
        ".rs": "Rust",
        ".zig": "Zig",
        ".swift": "Swift",
        ".m": "Objective-C",
        ".mm": "Objective-C++",
        ".lua": "Lua",
        ".sql": "SQL",
        ".graphql": "GraphQL",
        ".gql": "GraphQL",
        ".proto": "Protocol Buffers",
        ".html": "HTML",
        ".htm": "HTML",
        ".xhtml": "XHTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".sass": "Sass",
        ".less": "Less",
        ".vue": "Vue",
        ".svelte": "Svelte",
        ".astro": "Astro",
        ".ejs": "EJS",
        ".hbs": "Handlebars",
        ".handlebars": "Handlebars",
        ".mustache": "Mustache",
        ".njk": "Nunjucks",
        ".twig": "Twig",
        ".jinja": "Jinja",
        ".jinja2": "Jinja",
        ".tpl": "Template",
        ".conf": "Config",
        ".cfg": "Config",
        ".dockerignore": "Dockerignore",
        ".editorconfig": "EditorConfig",
        "Dockerfile": "Dockerfile",
        "Containerfile": "Containerfile",
        "Makefile": "Makefile",
        "CMakeLists.txt": "CMake",
        "Jenkinsfile": "Jenkinsfile",
        "Procfile": "Procfile",
        "Gemfile": "Ruby",
        "Rakefile": "Ruby",
        "Podfile": "Ruby",
        "Vagrantfile": "Ruby",
        "Brewfile": "Ruby",
    }
    return labels.get(target, target or "codigo")


@lru_cache(maxsize=None)
def _which(command_name):
    return shutil.which(command_name)


def _build_subprocess_env(extra_env=None):
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    env["LANGUAGE"] = "C"
    if extra_env:
        env.update(extra_env)
    return env


def _strip_tool_noise(output):
    cleaned = []
    for line in _normalize_text(output).split("\n"):
        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue
        if stripped.startswith("(node:") and "ExperimentalWarning" in stripped:
            continue
        if stripped.startswith("(Use `node --trace-warnings"):
            continue
        if stripped.startswith("Node.js v"):
            continue
        if stripped.startswith("bash: warning: setlocale:"):
            continue
        if stripped.startswith("perl: warning: Setting locale failed."):
            continue
        if stripped.startswith("perl: warning: Please check that your locale settings:"):
            continue
        if stripped.startswith("LC_ALL =") or stripped.startswith("LC_CTYPE =") or stripped.startswith("LANG ="):
            continue
        if stripped == 'are supported and installed on your system.':
            continue
        if stripped.startswith('perl: warning: Falling back to the standard locale'):
            continue
        if "DVTFilePathFSEvents" in stripped or "DVTDeveloperPaths" in stripped:
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _looks_like_syntax_error(message):
    return bool(SYNTAX_LIKE_MESSAGE_RE.search(message or ""))


def _line_excerpt(content, line_number):
    lines = _normalize_text(content).split("\n")
    if 1 <= line_number <= len(lines):
        return lines[line_number - 1]
    return ""


def _column_from_token(line_text, token, fallback=1):
    if not line_text or not token:
        return fallback
    index = line_text.find(token)
    if index >= 0:
        return index + 1
    return fallback


def _first_error_line(output):
    for line in output.split("\n"):
        if "error" in line.lower() or "syntax" in line.lower():
            return line.strip()
    return output.split("\n", 1)[0].strip()


def _parse_node_syntax_error(output, content):
    lines = output.split("\n")
    for index, line in enumerate(lines):
        match = re.search(r":(\d+)$", line.strip())
        if not match:
            continue
        line_number = int(match.group(1))
        caret_line = lines[index + 2] if index + 2 < len(lines) else ""
        column = caret_line.find("^") + 1 if "^" in caret_line else 1
        message = "Error de sintaxis"
        for candidate in lines[index + 3:]:
            stripped = candidate.strip()
            if stripped.startswith("SyntaxError:"):
                message = stripped.split("SyntaxError:", 1)[1].strip()
                break
        return _build_validation_result(
            supported=True,
            ok=False,
            message=message,
            line=line_number,
            column=column,
            end_line=line_number,
            end_column=column + 1,
            engine="node-check",
        )
    return None


def _parse_shell_syntax_error(output, content, engine_name):
    match = re.search(r": line (\d+): (.+)$", output, re.MULTILINE)
    if not match:
        return None
    line_number = int(match.group(1))
    message = match.group(2).strip()
    column = 1

    token_match = re.search(r"unexpected token `([^`]+)'", message)
    if token_match:
        column = _column_from_token(_line_excerpt(content, line_number), token_match.group(1), fallback=1)

    return _build_validation_result(
        supported=True,
        ok=False,
        message=message,
        line=line_number,
        column=column,
        end_line=line_number,
        end_column=column + 1,
        engine=engine_name,
    )


def _parse_ruby_syntax_error(output):
    lines = output.split("\n")
    for index, line in enumerate(lines):
        match = re.search(r":(\d+):\s+(.+)$", line)
        if not match:
            continue
        line_number = int(match.group(1))
        message = match.group(2).strip()
        source_line = lines[index + 1] if index + 1 < len(lines) else ""
        caret_line = lines[index + 2] if index + 2 < len(lines) else ""
        column = caret_line.find("^") + 1 if "^" in caret_line else 1
        end_column = column + max(caret_line.count("^"), 1)
        if not _looks_like_syntax_error(message):
            return None
        return _build_validation_result(
            supported=True,
            ok=False,
            message=message,
            line=line_number,
            column=column,
            end_line=line_number,
            end_column=end_column,
            engine="ruby-wc",
        )
    return None


def _parse_perl_syntax_error(output, content):
    match = re.search(r"syntax error at .* line (\d+), near \"([^\"]+)\"", output)
    if match:
        line_number = int(match.group(1))
        near_text = match.group(2)
        column = _column_from_token(_line_excerpt(content, line_number), near_text, fallback=1)
        return _build_validation_result(
            supported=True,
            ok=False,
            message=f"syntax error near {near_text}",
            line=line_number,
            column=column,
            end_line=line_number,
            end_column=column + max(len(near_text), 1),
            engine="perl-c",
        )

    match = re.search(r"Unmatched right curly bracket at .* line (\d+)", output)
    if match:
        line_number = int(match.group(1))
        line_text = _line_excerpt(content, line_number)
        column = line_text.rfind("}") + 1 if "}" in line_text else 1
        return _build_validation_result(
            supported=True,
            ok=False,
            message="Unmatched right curly bracket",
            line=line_number,
            column=column,
            end_line=line_number,
            end_column=column + 1,
            engine="perl-c",
        )
    return None


def _parse_file_colon_error(output, engine_name):
    match = re.search(r"(?m)^.*?:(\d+):(\d+):\s+error:\s+(.+)$", output)
    if not match:
        return None
    line_number = int(match.group(1))
    column = int(match.group(2))
    message = match.group(3).strip()
    if not _looks_like_syntax_error(message):
        return None
    return _build_validation_result(
        supported=True,
        ok=False,
        message=message,
        line=line_number,
        column=column,
        end_line=line_number,
        end_column=column + 1,
        engine=engine_name,
    )


def _parse_javac_error(output):
    lines = output.split("\n")
    for index, line in enumerate(lines):
        match = re.search(r":(\d+): error: (.+)$", line)
        if not match:
            continue
        line_number = int(match.group(1))
        message = match.group(2).strip()
        if not _looks_like_syntax_error(message):
            return None
        caret_line = lines[index + 2] if index + 2 < len(lines) else ""
        column = caret_line.find("^") + 1 if "^" in caret_line else 1
        return _build_validation_result(
            supported=True,
            ok=False,
            message=message,
            line=line_number,
            column=column,
            end_line=line_number,
            end_column=column + 1,
            engine="javac",
        )
    return None


def _parse_rust_error(output):
    message_match = re.search(r"(?m)^error:\s+(.+)$", output)
    line_match = re.search(r"(?m)^\s*-->\s+.*:(\d+):(\d+)$", output)
    if not message_match or not line_match:
        return None
    message = message_match.group(1).strip()
    if not _looks_like_syntax_error(message):
        return None
    line_number = int(line_match.group(1))
    column = int(line_match.group(2))
    return _build_validation_result(
        supported=True,
        ok=False,
        message=message,
        line=line_number,
        column=column,
        end_line=line_number,
        end_column=column + 1,
        engine="rustc",
    )


def _parse_dart_error(output):
    for line in output.split("\n"):
        parts = line.split("|")
        if len(parts) < 8 or parts[0] != "ERROR":
            continue
        issue_type = parts[1]
        message = parts[7].strip()
        if issue_type != "SYNTACTIC_ERROR" and not _looks_like_syntax_error(message):
            continue
        line_number = int(parts[4])
        column = int(parts[5])
        length = int(parts[6]) if parts[6].isdigit() else 1
        return _build_validation_result(
            supported=True,
            ok=False,
            message=message,
            line=line_number,
            column=column,
            end_line=line_number,
            end_column=column + max(length, 1),
            engine="dart-analyze",
        )
    return None


def _parse_make_error(output):
    match = re.search(r"(?m)^.*?:(\d+): \*\*\* (.+?)\.  Stop\.$", output)
    if not match:
        return None
    line_number = int(match.group(1))
    message = match.group(2).strip()
    return _build_validation_result(
        supported=True,
        ok=False,
        message=message,
        line=line_number,
        column=1,
        end_line=line_number,
        end_column=2,
        engine="make",
    )


def _run_tempfile_validator(
    content,
    file_path,
    *,
    command,
    error_parser,
    success_message,
    engine_name,
    extension=None,
    basename=None,
    cwd=None,
    extra_env=None,
):
    extension = extension or os.path.splitext(file_path or "")[1]
    basename = basename or os.path.basename(file_path or "") or f"snippet{extension or '.txt'}"
    source = _normalize_text(content)

    with tempfile.TemporaryDirectory(prefix="programita_syntax_") as temp_dir:
        temp_path = os.path.join(temp_dir, basename)
        with open(temp_path, "w", encoding="utf-8") as handle:
            handle.write(source)

        def resolve_template(value):
            if not isinstance(value, str):
                return value
            return (
                value
                .replace("{temp_path}", temp_path)
                .replace("{temp_dir}", temp_dir)
            )

        resolved_command = []
        for item in command:
            resolved_command.append(resolve_template(item))

        resolved_extra_env = {
            key: resolve_template(value)
            for key, value in (extra_env or {}).items()
        }

        run_cwd = cwd or os.path.dirname(file_path or "") or temp_dir
        completed = subprocess.run(
            resolved_command,
            cwd=run_cwd,
            capture_output=True,
            text=True,
            env=_build_subprocess_env(resolved_extra_env),
        )
        output = _strip_tool_noise(f"{completed.stdout}\n{completed.stderr}")

        parsed_error = error_parser(output, source) if error_parser else None
        if parsed_error:
            return parsed_error

        if completed.returncode == 0:
            return _build_validation_result(
                supported=True,
                ok=True,
                message=success_message,
                engine=engine_name,
            )

        return None


def _validate_python(content, file_path, _target):
    try:
        compile(_normalize_text(content), file_path or "<editor>", "exec")
        return _build_validation_result(
            supported=True,
            ok=True,
            message="Sintaxis Python correcta",
            engine="python-compile",
        )
    except SyntaxError as exc:
        return _build_validation_result(
            supported=True,
            ok=False,
            message=exc.msg or "Error de sintaxis",
            line=exc.lineno or 1,
            column=exc.offset or 1,
            end_line=getattr(exc, "end_lineno", None) or exc.lineno or 1,
            end_column=getattr(exc, "end_offset", None),
            engine="python-compile",
        )


def _strip_jsonc_comments(text):
    result = []
    in_string = False
    escape = False
    in_line_comment = False
    in_block_comment = False
    index = 0

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
                result.append("\n")
            else:
                result.append(" ")
            index += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                result.extend([" ", " "])
                in_block_comment = False
                index += 2
                continue
            result.append("\n" if char == "\n" else " ")
            index += 1
            continue

        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == "/" and next_char == "/":
            result.extend([" ", " "])
            in_line_comment = True
            index += 2
            continue

        if char == "/" and next_char == "*":
            result.extend([" ", " "])
            in_block_comment = True
            index += 2
            continue

        result.append(char)
        index += 1

    return "".join(result)


def _strip_jsonc_trailing_commas(text):
    chars = list(text)
    in_string = False
    escape = False

    for index, char in enumerate(chars):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char != ",":
            continue

        lookahead = index + 1
        while lookahead < len(chars) and chars[lookahead] in " \t\r\n":
            lookahead += 1
        if lookahead < len(chars) and chars[lookahead] in "]}":
            chars[index] = " "

    return "".join(chars)


def _validate_json(content, _file_path, _target):
    try:
        json.loads(_normalize_text(content))
        return _build_validation_result(
            supported=True,
            ok=True,
            message="JSON valido",
            engine="json",
        )
    except json.JSONDecodeError as exc:
        return _build_validation_result(
            supported=True,
            ok=False,
            message=exc.msg or "JSON invalido",
            line=exc.lineno or 1,
            column=exc.colno or 1,
            end_line=exc.lineno or 1,
            end_column=(exc.colno or 1) + 1,
            engine="json",
        )


def _validate_jsonc(content, file_path, _target):
    prepared = _strip_jsonc_trailing_commas(_strip_jsonc_comments(_normalize_text(content)))
    return _validate_json(prepared, file_path, ".json")


def _validate_toml(content, _file_path, _target):
    if tomllib is None:
        return None
    try:
        tomllib.loads(_normalize_text(content))
        return _build_validation_result(
            supported=True,
            ok=True,
            message="TOML valido",
            engine="tomllib",
        )
    except tomllib.TOMLDecodeError as exc:
        line = getattr(exc, "lineno", None) or 1
        column = getattr(exc, "colno", None) or 1
        return _build_validation_result(
            supported=True,
            ok=False,
            message=str(exc) or "TOML invalido",
            line=line,
            column=column,
            end_line=line,
            end_column=column + 1,
            engine="tomllib",
        )


def _validate_yaml(content, _file_path, _target):
    if yaml is None:
        return None
    try:
        yaml.safe_load(_normalize_text(content))
        return _build_validation_result(
            supported=True,
            ok=True,
            message="YAML valido",
            engine="pyyaml",
        )
    except yaml.MarkedYAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = (mark.line + 1) if mark else 1
        column = (mark.column + 1) if mark else 1
        message = getattr(exc, "problem", None) or str(exc) or "YAML invalido"
        return _build_validation_result(
            supported=True,
            ok=False,
            message=message,
            line=line,
            column=column,
            end_line=line,
            end_column=column + 1,
            engine="pyyaml",
        )


def _validate_xml(content, _file_path, _target):
    try:
        ET.fromstring(_normalize_text(content))
        return _build_validation_result(
            supported=True,
            ok=True,
            message="XML valido",
            engine="xml",
        )
    except ET.ParseError as exc:
        line = 1
        column = 1
        if hasattr(exc, "position") and exc.position:
            line, column = exc.position
        return _build_validation_result(
            supported=True,
            ok=False,
            message=str(exc) or "XML invalido",
            line=line,
            column=(column + 1) if column is not None else 1,
            end_line=line,
            end_column=(column + 2) if column is not None else None,
            engine="xml",
        )


def _validate_ini(content, _file_path, _target):
    parser = configparser.ConfigParser(allow_no_value=True)
    try:
        parser.read_string(_normalize_text(content))
        return _build_validation_result(
            supported=True,
            ok=True,
            message="Configuracion INI valida",
            engine="configparser",
        )
    except configparser.Error as exc:
        line = getattr(exc, "lineno", None) or 1
        return _build_validation_result(
            supported=True,
            ok=False,
            message=str(exc),
            line=line,
            column=1,
            end_line=line,
            end_column=2,
            engine="configparser",
        )


def _validate_properties(content, _file_path, _target):
    lines = _normalize_text(content).split("\n")
    for line_number, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("!"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            continue

        separator_index = None
        escape = False
        for index, char in enumerate(raw_line):
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char in ("=", ":"):
                separator_index = index
                break

        if separator_index is None:
            whitespace_match = re.search(r"(?<!\\)\s+", raw_line)
            separator_index = whitespace_match.start() if whitespace_match else None

        if separator_index is None:
            return _build_validation_result(
                supported=True,
                ok=False,
                message="Falta un separador de clave/valor",
                line=line_number,
                column=len(raw_line) + 1,
                end_line=line_number,
                end_column=len(raw_line) + 2,
                engine="properties",
            )

    return _build_validation_result(
        supported=True,
        ok=True,
        message="Properties valido",
        engine="properties",
    )


def _validate_procfile(content, _file_path, _target):
    lines = _normalize_text(content).split("\n")
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            return _build_validation_result(
                supported=True,
                ok=False,
                message="Cada linea debe seguir el formato proceso: comando",
                line=line_number,
                column=1,
                end_line=line_number,
                end_column=len(line) + 1,
                engine="procfile",
            )
        process_name, command_text = stripped.split(":", 1)
        if not process_name.strip():
            return _build_validation_result(
                supported=True,
                ok=False,
                message="Falta el nombre del proceso",
                line=line_number,
                column=1,
                end_line=line_number,
                end_column=2,
                engine="procfile",
            )
        if not command_text.strip():
            return _build_validation_result(
                supported=True,
                ok=False,
                message="Falta el comando del proceso",
                line=line_number,
                column=line.find(":") + 2,
                end_line=line_number,
                end_column=len(line) + 1,
                engine="procfile",
            )

    return _build_validation_result(
        supported=True,
        ok=True,
        message="Procfile valido",
        engine="procfile",
    )


def _validate_dockerfile(content, _file_path, target):
    pending = []
    pending_start_line = None
    lines = _normalize_text(content).split("\n")

    for line_number, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if pending_start_line is None:
            pending_start_line = line_number
        pending.append(stripped)

        if stripped.endswith("\\"):
            continue

        logical_line = " ".join(part[:-1].rstrip() if part.endswith("\\") else part for part in pending).strip()
        pending = []
        first_token = logical_line.split(None, 1)[0].upper() if logical_line else ""
        if first_token not in DOCKERFILE_INSTRUCTIONS:
            return _build_validation_result(
                supported=True,
                ok=False,
                message=f"Instruccion Docker desconocida: {first_token or logical_line}",
                line=pending_start_line,
                column=1,
                end_line=pending_start_line,
                end_column=max(len(first_token), 1) + 1,
                engine=target,
            )
        pending_start_line = None

    if pending:
        return _build_validation_result(
            supported=True,
            ok=False,
            message="Linea continuada sin cierre",
            line=pending_start_line or 1,
            column=1,
            end_line=pending_start_line or 1,
            end_column=2,
            engine=target,
        )

    return _build_validation_result(
        supported=True,
        ok=True,
        message=f"{target} valido",
        engine=target,
    )


def _validate_makefile(content, file_path, _target):
    if not _which("make"):
        return None
    return _run_tempfile_validator(
        content,
        file_path,
        command=["make", "-f", "{temp_path}", "-n", "-r", "-R", "-s", "all"],
        error_parser=lambda output, source: _parse_make_error(output),
        success_message="Makefile valido",
        engine_name="make",
        basename="Makefile",
    )


def _validate_cmake_lists(content, _file_path, _target):
    delimiter_result = _validate_generic_delimiters(content, "CMake", target="CMakeLists.txt")
    if delimiter_result:
        return delimiter_result

    openers = {
        "if": "endif",
        "foreach": "endforeach",
        "function": "endfunction",
        "macro": "endmacro",
        "while": "endwhile",
        "block": "endblock",
    }
    closers = {value: key for key, value in openers.items()}
    stack = []

    for line_number, line in enumerate(_normalize_text(content).split("\n"), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        open_match = re.match(r"(?i)^(if|foreach|function|macro|while|block)\s*\(", stripped)
        if open_match:
            token = open_match.group(1).lower()
            stack.append((token, line_number))
            continue

        close_match = re.match(r"(?i)^(endif|endforeach|endfunction|endmacro|endwhile|endblock)\s*(?:\(|$)", stripped)
        if close_match:
            token = close_match.group(1).lower()
            if not stack:
                return _build_validation_result(
                    supported=True,
                    ok=False,
                    message=f"Cierre inesperado: {token}",
                    line=line_number,
                    column=1,
                    end_line=line_number,
                    end_column=len(token) + 1,
                    engine="cmake-heuristic",
                )
            expected = closers[token]
            current, open_line = stack.pop()
            if current != expected:
                return _build_validation_result(
                    supported=True,
                    ok=False,
                    message=f"Se esperaba {openers[current]} y se encontro {token}",
                    line=line_number,
                    column=1,
                    end_line=line_number,
                    end_column=len(token) + 1,
                    engine="cmake-heuristic",
                )

    if stack:
        token, line_number = stack[-1]
        return _build_validation_result(
            supported=True,
            ok=False,
            message=f"Bloque {token} sin cierre {openers[token]}",
            line=line_number,
            column=1,
            end_line=line_number,
            end_column=len(token) + 1,
            engine="cmake-heuristic",
        )

    return _build_validation_result(
        supported=True,
        ok=True,
        message="Sintaxis CMake estructuralmente correcta",
        engine="cmake-heuristic",
    )


def _line_comments_for_target(target):
    comments = []
    if target in LINE_COMMENT_TARGETS or target in RUBY_DSL_FILENAMES or target in DOCKERFILE_FILENAMES or target in CMAKE_FILENAMES or target in MAKE_FILENAMES or target in PROCFILE_FILENAMES:
        comments.append("#")
    if target in C_STYLE_COMMENT_TARGETS or target == "Jenkinsfile":
        comments.append("//")
    if target in DASH_COMMENT_TARGETS:
        comments.append("--")
    return comments


def _block_comments_for_target(target):
    comments = []
    if target in C_STYLE_COMMENT_TARGETS or target == "Jenkinsfile":
        comments.append(("/*", "*/"))
    if target in HTML_COMMENT_TARGETS:
        comments.append(("<!--", "-->"))
    return comments


def _quote_chars_for_target(target):
    quotes = {'"', "'"}
    if target in BACKTICK_STRING_TARGETS:
        quotes.add("`")
    return quotes


def _validate_generic_delimiters(content, label, *, target=None):
    text = _normalize_text(content)
    stack = []
    line_comments = _line_comments_for_target(target)
    block_comments = _block_comments_for_target(target)
    quote_chars = _quote_chars_for_target(target)

    in_string = None
    escape = False
    block_comment = None
    line = 1
    column = 1
    index = 0

    while index < len(text):
        char = text[index]

        if block_comment:
            end_token = block_comment[1]
            if text.startswith(end_token, index):
                index += len(end_token)
                column += len(end_token)
                block_comment = None
                continue
            if char == "\n":
                line += 1
                column = 1
            else:
                column += 1
            index += 1
            continue

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
            if char == "\n":
                line += 1
                column = 1
            else:
                column += 1
            index += 1
            continue

        if char == "\n":
            line += 1
            column = 1
            index += 1
            continue

        line_comment = next((token for token in line_comments if text.startswith(token, index)), None)
        if line_comment:
            while index < len(text) and text[index] != "\n":
                index += 1
            continue

        block_comment_token = next((token for token in block_comments if text.startswith(token[0], index)), None)
        if block_comment_token:
            block_comment = block_comment_token
            index += len(block_comment_token[0])
            column += len(block_comment_token[0])
            continue

        if char in quote_chars:
            in_string = char
            column += 1
            index += 1
            continue

        if char in "([{":
            stack.append((char, line, column))
        elif char in ")]}":
            if not stack:
                return _build_validation_result(
                    supported=True,
                    ok=False,
                    message=f"Cierre inesperado {char}",
                    line=line,
                    column=column,
                    end_line=line,
                    end_column=column + 1,
                    engine="delimiter-heuristic",
                )
            opener, open_line, open_column = stack.pop()
            pairs = {"(": ")", "[": "]", "{": "}"}
            expected = pairs[opener]
            if char != expected:
                return _build_validation_result(
                    supported=True,
                    ok=False,
                    message=f"Se esperaba {expected} para cerrar {opener}",
                    line=line,
                    column=column,
                    end_line=line,
                    end_column=column + 1,
                    engine="delimiter-heuristic",
                )

        column += 1
        index += 1

    if in_string:
        return _build_validation_result(
            supported=True,
            ok=False,
            message="Cadena sin cerrar",
            line=line,
            column=column,
            end_line=line,
            end_column=column + 1,
            engine="delimiter-heuristic",
        )

    if block_comment:
        return _build_validation_result(
            supported=True,
            ok=False,
            message="Comentario de bloque sin cerrar",
            line=line,
            column=column,
            end_line=line,
            end_column=column + 1,
            engine="delimiter-heuristic",
        )

    if stack:
        opener, open_line, open_column = stack[-1]
        return _build_validation_result(
            supported=True,
            ok=False,
            message=f"Delimitador {opener} sin cerrar",
            line=open_line,
            column=open_column,
            end_line=open_line,
            end_column=open_column + 1,
            engine="delimiter-heuristic",
        )

    return None


def _validate_markup_structure(content, label):
    text = _normalize_text(content)
    tag_pattern = re.compile(r'<!--.*?-->|<!\[CDATA\[.*?\]\]>|<\?.*?\?>|</?\s*([A-Za-z][\w:.-]*)\b[^<>]*?/?>', re.DOTALL)
    stack = []

    for match in tag_pattern.finditer(text):
        token = match.group(0)
        tag_name = match.group(1)
        if not tag_name:
            continue

        lower_name = tag_name.lower()
        if lower_name in HTML_VOID_TAGS:
            continue

        is_closing = token.lstrip().startswith("</")
        is_self_closing = token.rstrip().endswith("/>")
        line_number = text.count("\n", 0, match.start()) + 1

        if is_self_closing:
            continue

        if not is_closing:
            stack.append((lower_name, tag_name, line_number))
            continue

        if not stack:
            return _build_validation_result(
                supported=True,
                ok=False,
                message=f"Etiqueta de cierre inesperada </{tag_name}>",
                line=line_number,
                column=1,
                end_line=line_number,
                end_column=len(tag_name) + 4,
                engine="markup-heuristic",
            )

        open_lower, open_name, open_line = stack.pop()
        if open_lower != lower_name:
            return _build_validation_result(
                supported=True,
                ok=False,
                message=f"Se esperaba </{open_name}> y se encontro </{tag_name}>",
                line=line_number,
                column=1,
                end_line=line_number,
                end_column=len(tag_name) + 4,
                engine="markup-heuristic",
            )

    if stack:
        _, open_name, open_line = stack[-1]
        return _build_validation_result(
            supported=True,
            ok=False,
            message=f"Etiqueta <{open_name}> sin cierre",
            line=open_line,
            column=1,
            end_line=open_line,
            end_column=len(open_name) + 2,
            engine="markup-heuristic",
        )

    return _build_validation_result(
        supported=True,
        ok=True,
        message=f"Estructura {label} correcta (heuristica)",
        engine="markup-heuristic",
    )


def _validate_end_keywords(content, label):
    open_pattern = re.compile(r'\b(?:def|defp|defmacro|defmacrop|defmodule|class|module|function|if|unless|case|begin|while|until|for|try|receive|fn|do)\b')
    close_pattern = re.compile(r'\bend\b')
    depth = 0
    last_open_line = None

    for line_number, line in enumerate(_normalize_text(content).split("\n"), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("--"):
            continue

        opens = len(open_pattern.findall(stripped))
        closes = len(close_pattern.findall(stripped))

        if opens:
            last_open_line = line_number
            depth += opens
        if closes:
            depth -= closes
            if depth < 0:
                column = stripped.lower().find("end") + 1
                return _build_validation_result(
                    supported=True,
                    ok=False,
                    message="end inesperado",
                    line=line_number,
                    column=column,
                    end_line=line_number,
                    end_column=column + 3,
                    engine="end-heuristic",
                )

    if depth > 0:
        return _build_validation_result(
            supported=True,
            ok=False,
            message="Bloque sin cerrar con end",
            line=last_open_line or 1,
            column=1,
            end_line=last_open_line or 1,
            end_column=2,
            engine="end-heuristic",
        )

    return _build_validation_result(
        supported=True,
        ok=True,
        message=f"Estructura {label} correcta (heuristica)",
        engine="end-heuristic",
    )


def _validate_structural_fallback(content, file_path, target):
    label = _language_label(target)

    delimiter_result = _validate_generic_delimiters(content, label, target=target)
    if delimiter_result:
        return delimiter_result

    if target in HTML_LIKE_TARGETS:
        return _validate_markup_structure(content, label)

    if target in END_STYLE_TARGETS:
        return _validate_end_keywords(content, label)

    return _build_validation_result(
        supported=True,
        ok=True,
        message=f"Validacion estructural de {label} correcta (heuristica)",
        engine="heuristic",
    )


def _validate_javascript(content, file_path, target):
    if not _which("node"):
        return None
    return _run_tempfile_validator(
        content,
        file_path,
        command=["node", "--check", "{temp_path}"],
        error_parser=lambda output, source: _parse_node_syntax_error(output, source),
        success_message="Sintaxis JavaScript correcta",
        engine_name="node-check",
        extension=target,
    )


def _validate_typescript(content, file_path, target):
    if target == ".ts" and _which("node"):
        result = _run_tempfile_validator(
            content,
            file_path,
            command=["node", "--experimental-strip-types", "--check", "{temp_path}"],
            error_parser=lambda output, source: _parse_node_syntax_error(output, source),
            success_message="Sintaxis TypeScript correcta",
            engine_name="node-strip-types",
            extension=target,
        )
        if result:
            return result
    return None


def _validate_shell(content, file_path, target):
    command_name = {
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "zsh",
        ".fish": "fish",
    }.get(target)
    if not command_name:
        return None

    resolved = _which(command_name)
    if not resolved:
        return None

    if target == ".fish":
        command = [resolved, "--no-execute", "{temp_path}"]
    else:
        command = [resolved, "-n", "{temp_path}"]

    return _run_tempfile_validator(
        content,
        file_path,
        command=command,
        error_parser=lambda output, source: _parse_shell_syntax_error(output, source, f"{command_name}-n"),
        success_message=f"Sintaxis {_language_label(target)} correcta",
        engine_name=f"{command_name}-n",
        extension=target,
    )


def _validate_ruby(content, file_path, target):
    if not _which("ruby"):
        return None
    basename = os.path.basename(file_path or "")
    if target in RUBY_DSL_FILENAMES:
        basename = target
    return _run_tempfile_validator(
        content,
        file_path,
        command=["ruby", "-wc", "{temp_path}"],
        error_parser=lambda output, source: _parse_ruby_syntax_error(output),
        success_message=f"Sintaxis {_language_label(target)} correcta",
        engine_name="ruby-wc",
        extension=os.path.splitext(file_path or "")[1],
        basename=basename or "snippet.rb",
    )


def _validate_perl(content, file_path, _target):
    if not _which("perl"):
        return None
    return _run_tempfile_validator(
        content,
        file_path,
        command=["perl", "-c", "{temp_path}"],
        error_parser=lambda output, source: _parse_perl_syntax_error(output, source),
        success_message="Sintaxis Perl correcta",
        engine_name="perl-c",
        extension=os.path.splitext(file_path or "")[1] or ".pl",
    )


def _validate_clang_family(content, file_path, target):
    tool_name = "clang++" if target in {".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx", ".mm"} else "clang"
    if not _which(tool_name):
        return None

    command = [tool_name, "-fsyntax-only", "-Wno-everything"]
    if target == ".m":
        command += ["-x", "objective-c"]
    elif target == ".mm":
        command += ["-x", "objective-c++"]
    command += ["{temp_path}"]

    return _run_tempfile_validator(
        content,
        file_path,
        command=command,
        error_parser=lambda output, source: _parse_file_colon_error(output, tool_name),
        success_message=f"Sintaxis {_language_label(target)} correcta",
        engine_name=tool_name,
        extension=target,
    )


def _validate_javac(content, file_path, _target):
    if not _which("javac"):
        return None
    basename = os.path.basename(file_path or "") or "Snippet.java"
    if not basename.endswith(".java"):
        basename = "Snippet.java"
    return _run_tempfile_validator(
        content,
        file_path,
        command=["javac", "-proc:none", "-implicit:none", "-Xmaxerrs", "1", "{temp_path}"],
        error_parser=lambda output, source: _parse_javac_error(output),
        success_message="Sintaxis Java correcta",
        engine_name="javac",
        basename=basename,
        extension=".java",
    )


def _validate_swift(content, file_path, _target):
    if not _which("swiftc"):
        return None
    return _run_tempfile_validator(
        content,
        file_path,
        command=["swiftc", "-frontend", "-parse", "-module-cache-path", "{temp_dir}/cache", "{temp_path}"],
        error_parser=lambda output, source: _parse_file_colon_error(output, "swift-parse"),
        success_message="Sintaxis Swift correcta",
        engine_name="swift-parse",
        extension=".swift",
    )


def _validate_rust(content, file_path, _target):
    if not _which("rustc"):
        return None
    basename = os.path.basename(file_path or "") or "snippet.rs"
    return _run_tempfile_validator(
        content,
        file_path,
        command=["rustc", "--emit", "metadata", "-o", "{temp_dir}/out.rmeta", "{temp_path}"],
        error_parser=lambda output, source: _parse_rust_error(output),
        success_message="Sintaxis Rust correcta",
        engine_name="rustc",
        basename=basename,
        extension=".rs",
    )


def _validate_dart(content, file_path, _target):
    if not _which("dart"):
        return None
    return _run_tempfile_validator(
        content,
        file_path,
        command=["dart", "--disable-analytics", "analyze", "--format", "machine", "{temp_path}"],
        error_parser=lambda output, source: _parse_dart_error(output),
        success_message="Sintaxis Dart correcta",
        engine_name="dart-analyze",
        extension=".dart",
        extra_env={
            "HOME": "{temp_dir}",
            "DART_SUPPRESS_ANALYTICS": "true",
            "FLUTTER_SUPPRESS_ANALYTICS": "true",
        },
    )


EXACT_VALIDATORS = {
    ".py": _validate_python,
    ".pyw": _validate_python,
    ".json": _validate_json,
    ".jsonc": _validate_jsonc,
    ".toml": _validate_toml,
    ".yml": _validate_yaml,
    ".yaml": _validate_yaml,
    ".xml": _validate_xml,
    ".xsd": _validate_xml,
    ".xsl": _validate_xml,
    ".wsdl": _validate_xml,
    ".svg": _validate_xml,
    ".ini": _validate_ini,
    ".editorconfig": _validate_ini,
    ".properties": _validate_properties,
    "Procfile": _validate_procfile,
    "Dockerfile": _validate_dockerfile,
    "Containerfile": _validate_dockerfile,
    "Makefile": _validate_makefile,
    "CMakeLists.txt": _validate_cmake_lists,
}

EXTERNAL_VALIDATORS = {
    ".js": _validate_javascript,
    ".mjs": _validate_javascript,
    ".cjs": _validate_javascript,
    ".ts": _validate_typescript,
    ".sh": _validate_shell,
    ".bash": _validate_shell,
    ".zsh": _validate_shell,
    ".fish": _validate_shell,
    ".rb": _validate_ruby,
    ".pl": _validate_perl,
    ".pm": _validate_perl,
    ".c": _validate_clang_family,
    ".cc": _validate_clang_family,
    ".cpp": _validate_clang_family,
    ".cxx": _validate_clang_family,
    ".h": _validate_clang_family,
    ".hh": _validate_clang_family,
    ".hpp": _validate_clang_family,
    ".hxx": _validate_clang_family,
    ".m": _validate_clang_family,
    ".mm": _validate_clang_family,
    ".java": _validate_javac,
    ".swift": _validate_swift,
    ".rs": _validate_rust,
    ".dart": _validate_dart,
    "Gemfile": _validate_ruby,
    "Rakefile": _validate_ruby,
    "Podfile": _validate_ruby,
    "Vagrantfile": _validate_ruby,
    "Brewfile": _validate_ruby,
}


def is_supported_syntax_target(file_path):
    return _target_from_path(file_path) is not None


def validate_code_syntax(content, file_path):
    target = _target_from_path(file_path)
    if not target:
        return _unknown_target_result(file_path)

    normalized = _normalize_text(content)

    exact_validator = EXACT_VALIDATORS.get(target)
    if exact_validator:
        result = exact_validator(normalized, file_path, target)
        if result:
            return result

    external_validator = EXTERNAL_VALIDATORS.get(target)
    if external_validator:
        result = external_validator(normalized, file_path, target)
        if result:
            return result

    return _validate_structural_fallback(normalized, file_path, target)
