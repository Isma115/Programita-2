import ast
from bisect import bisect_right
import json
import os
import re
import subprocess

from lxml import etree, html

class ProjectManager:
    """
    Manages the loading and scanning of project files.
    """
    IGNORED_DIRECTORIES = {
        '.git', '__pycache__', 'node_modules', 'venv', 'env',
        '.idea', '.vscode', '.next', 'dist', 'build', 'memoria'
    }
    
    # Supported code extensions
    CODE_EXTENSIONS = {
        '.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp', '.hxx',
        '.cs', '.vb', '.fs', '.fsx',
        '.go', '.rs', '.zig',
        '.java', '.kt', '.kts', '.scala', '.groovy', '.gradle',
        '.swift', '.m', '.mm',
        '.py', '.pyw', '.rb', '.php', '.phtml',
        '.pl', '.pm', '.lua', '.r', '.jl', '.dart',
        '.ex', '.exs', '.erl', '.hrl',
        '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
        '.html', '.htm', '.xhtml', '.css', '.scss', '.sass', '.less',
        '.vue', '.svelte', '.astro',
        '.ejs', '.hbs', '.handlebars', '.mustache', '.njk', '.twig', '.jinja', '.jinja2', '.tpl',
        '.sql', '.graphql', '.gql', '.proto',
        '.json', '.jsonc', '.xml', '.xsd', '.xsl', '.wsdl',
        '.yml', '.yaml', '.toml', '.ini', '.cfg', '.conf', '.properties',
        '.sh', '.bash', '.zsh', '.fish', '.bat', '.cmd', '.ps1', '.psm1', '.psd1',
        '.dockerignore', '.editorconfig'
    }
    DEFAULT_HIDDEN_CODE_EXTENSIONS = {'.json', '.jsonc'}
    CODE_FILENAMES = {
        'Dockerfile', 'Containerfile', 'Makefile', 'CMakeLists.txt',
        'Jenkinsfile', 'Procfile', 'Rakefile', 'Gemfile', 'Podfile',
        'Brewfile', 'Vagrantfile'
    }
    MARKUP_EXTENSIONS = {
        '.html', '.htm', '.xhtml', '.xml', '.xsd', '.xsl', '.wsdl',
        '.jsx', '.tsx', '.vue', '.svelte', '.astro',
        '.ejs', '.hbs', '.handlebars', '.mustache', '.njk', '.twig', '.jinja', '.jinja2', '.tpl'
    }
    HTML_AST_EXTENSIONS = {'.html', '.htm', '.xhtml'}
    XML_AST_EXTENSIONS = {'.xml', '.xsd', '.xsl', '.wsdl'}
    JS_AST_EXTENSIONS = {'.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx'}
    CSS_STRUCTURE_EXTENSIONS = {'.css', '.scss', '.sass', '.less'}
    BRACE_STYLE_EXTENSIONS = {
        '.c', '.cc', '.cpp', '.cxx', '.h', '.hh', '.hpp', '.hxx',
        '.cs', '.go', '.rs', '.zig',
        '.java', '.kt', '.kts', '.scala', '.groovy', '.gradle',
        '.swift', '.m', '.mm',
        '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
        '.php', '.phtml', '.dart',
        '.css', '.scss', '.sass', '.less',
        '.vue', '.svelte', '.astro',
        '.graphql', '.gql', '.proto',
        '.json', '.jsonc'
    }
    END_STYLE_EXTENSIONS = {
        '.rb', '.lua', '.ex', '.exs', '.erl', '.hrl'
    }
    JS_AST_HELPER_PATH = os.path.join(os.path.dirname(__file__), "js_ast_structures.js")
    CSS_KEYFRAME_STEP_RE = re.compile(
        r'^(?:from|to|\d+(?:\.\d+)?%)\s*(?:,\s*(?:from|to|\d+(?:\.\d+)?%))*$',
        re.IGNORECASE
    )
    CSS_PROPERTY_GROUP_RE = re.compile(r'^(?:--)?[A-Za-z_][\w-]*\s*:\s*$')
    CSS_ELEMENT_SELECTOR_RE = re.compile(r'^(?:\*|[A-Za-z][\w-]*)(?:\s+(?:\*|[A-Za-z][\w-]*))*$')

    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.current_project_path = None
        self.files = [] # List of dicts: {'path': absolute_path, 'rel_path': relative_path, 'content': str}

    def load_project(self, path):
        """
        Loads a project from the given path.
        Scans all files recursively.
        """
        if not os.path.isdir(path):
            raise ValueError(f"Invalid directory path: {path}")

        self.current_project_path = path
        self.files = []
        
        self._scan_directory(path)
        print(f"ProjectManager: Loaded {len(self.files)} files from {path}")

    def _scan_directory(self, path):
        """
        Recursively scans the directory for code files.
        """
        for root, _, filenames in os.walk(path):
            # Skip common junk directories
            if any(part.startswith('.') or part in self.IGNORED_DIRECTORIES for part in root.split(os.sep)):
                continue
                
            for filename in filenames:
                if self.is_code_file(filename):
                    full_path = os.path.join(root, filename)
                    try:
                        # Attempt to read file content to cache it (or at least verify it's text)
                        # For large projects, we might want to lazy load, but requirement says "read content" for prompt gen
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                        self.files.append({
                            'path': full_path,
                            'rel_path': os.path.relpath(full_path, self.current_project_path),
                            'content': content
                        })
                    except Exception as e:
                        print(f"Error reading file {full_path}: {e}")

    def get_files(self):
        """Returns the list of loaded files."""
        return self.files

    def get_project_tree_text(self):
        """Returns a text tree representation of the current project."""
        if not self.current_project_path or not os.path.isdir(self.current_project_path):
            return ""

        root_path = self.current_project_path
        root_name = os.path.basename(os.path.normpath(root_path)) or root_path
        lines = [root_name + "/"]

        def should_skip(name):
            return name.startswith('.') or name in self.IGNORED_DIRECTORIES

        def walk(directory_path, prefix=""):
            try:
                entries = sorted(os.listdir(directory_path), key=lambda item: (not os.path.isdir(os.path.join(directory_path, item)), item.lower()))
            except Exception as e:
                lines.append(f"{prefix}[Error leyendo directorio: {e}]")
                return

            visible_entries = [entry for entry in entries if not should_skip(entry)]
            for index, entry in enumerate(visible_entries):
                full_path = os.path.join(directory_path, entry)
                is_last = index == len(visible_entries) - 1
                branch = "└── " if is_last else "├── "
                suffix = "/" if os.path.isdir(full_path) else ""
                lines.append(f"{prefix}{branch}{entry}{suffix}")
                if os.path.isdir(full_path):
                    child_prefix = prefix + ("    " if is_last else "│   ")
                    walk(full_path, child_prefix)

        walk(root_path)
        return "\n".join(lines)

    @classmethod
    def is_code_file(cls, filename):
        """Returns True if the file should be treated as code/config/source."""
        basename = os.path.basename(filename)
        ext = os.path.splitext(basename)[1].lower()
        return ext in cls.CODE_EXTENSIONS or basename in cls.CODE_FILENAMES

    @classmethod
    def is_default_code_file(cls, filename):
        """Returns True if the file should appear in Code view with no explicit extension filter."""
        basename = os.path.basename(filename)
        ext = os.path.splitext(basename)[1].lower()
        if basename in cls.CODE_FILENAMES:
            return True
        return ext in cls.CODE_EXTENSIONS and ext not in cls.DEFAULT_HIDDEN_CODE_EXTENSIONS



    def find_relevant_files(self, user_query, relevant_files_subset=None, min_files=0, max_files=None):
        """
        Finds files that are most relevant to the user_query.
        This is a simple heuristic based on keyword overlap.
        
        Args:
            user_query: The user's text description.
            relevant_files_subset: Optional list of file dicts to search within. 
                                   If None, searches all project files.
            min_files: The minimum number of files to return (pads with score 0 files if needed).
            max_files: Optional maximum number of files to return after padding.
        
        Returns:
            List of file dicts sorted by relevance.
        """
        target_files = relevant_files_subset if relevant_files_subset is not None else self.files
        if not target_files:
            return []

        scored_files = []
        query_tokens = set(user_query.lower().split())

        for file in target_files:
            score = 0
            content_lower = file['content'].lower()
            path_lower = file['rel_path'].lower()
            
            # Simple scoring:
            # +10 for filename matching tokens
            # +1 for content matching tokens
            
            for token in query_tokens:
                if len(token) < 3: continue # Skip short words
                
                if token in path_lower:
                    score += 10
                if token in content_lower:
                    # Count occurrences (capped to avoid dominance by large files)
                    count = content_lower.count(token)
                    score += min(count, 5) 
            
            scored_files.append((score, file))

        # Sort by score descending
        scored_files.sort(key=lambda x: x[0], reverse=True)
        
        # Take all files with score > 0
        relevant = [f[1] for f in scored_files if f[0] > 0]
        
        # If we have less than min_files matching files, pad with the rest
        if len(relevant) < min_files:
            relevant = [f[1] for f in scored_files][:min_files]

        if max_files is not None:
            try:
                max_files = max(int(max_files), int(min_files))
            except (TypeError, ValueError):
                max_files = None
            if max_files is not None:
                relevant = relevant[:max_files]
            
        return relevant

    def replace_region(self, region_name, new_content):
        """
        Searches for a region by name across all loaded files and replaces it.
        Supports multiple comment styles:
        - // #region "name" ... // #endregion (JS/TS/C++/Java)
        - # #region "name" ... # #endregion (Python/Shell)
        - -- #region "name" ... -- #endregion (SQL/Lua)
        - /* #region "name" */ ... /* #endregion */ (CSS/C)
        - <!-- #region "name" --> ... <!-- #endregion --> (HTML/XML)
        """
        found = False
        escaped_name = re.escape(region_name)
        
        # Pattern that matches region blocks with various comment styles
        # Supports:
        # - Line comments: //, #, -- followed by optional #region or just region
        # - Block comments: /* */ and <!-- -->
        # The endregion can also use #endregion or just endregion
        regex_pattern = (
            rf'([ \t]*'
            rf'(?:'
            # Line comment styles: //, #, --
            rf'(?://|#|--)[ \t]*#?region[ \t]+["\']?{escaped_name}["\']?.*?'
            rf'(?://|#|--)[ \t]*#?endregion'
            rf'|'
            # Block comment style: /* */
            rf'/\*[ \t]*#?region[ \t]+["\']?{escaped_name}["\']?.*?#?endregion[ \t]*\*/'
            rf'|'
            # HTML comment style: <!-- -->
            rf'<!--[ \t]*#?region[ \t]+["\']?{escaped_name}["\']?.*?#?endregion[ \t]*-->'
            rf')'
            rf')'
        )
        
        for file_data in self.files:
            content = file_data['content']
            if not content:
                continue
                
            new_file_content, count = re.subn(regex_pattern, new_content, content, flags=re.DOTALL | re.IGNORECASE)
            
            if count > 0:
                print(f"ProjectManager: Replaced region '{region_name}' in {file_data['rel_path']}")
                file_data['content'] = new_file_content
                # Save to disk
                try:
                    with open(file_data['path'], 'w', encoding='utf-8') as f:
                        f.write(new_file_content)
                    found = True
                except Exception as e:
                    print(f"ProjectManager: Error saving file {file_data['path']}: {e}")
                    
        return found

    def get_non_code_files(self):
        """
        Scans the project directory for files NOT in CODE_EXTENSIONS.
        Returns list of dicts: {'path': abs_path, 'rel_path': relative_path}
        """
        if not self.current_project_path:
            return []

        non_code = []
        for root, dirs, filenames in os.walk(self.current_project_path):
            # Filter dirs in-place to skip ignored
            dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRECTORIES and not d.startswith('.')]

            for filename in filenames:
                if filename.startswith('.'):
                    continue
                if not self.is_code_file(filename):
                    full_path = os.path.join(root, filename)
                    non_code.append({
                        'path': full_path,
                        'rel_path': os.path.relpath(full_path, self.current_project_path)
                    })

        return non_code

    def extract_functions(self, file_paths=None):
        """
        Extracts code structures using AST parsers when available.
        Python uses the stdlib AST, JS/TS/JSX/TSX use a Node-based AST helper,
        and HTML/XML use lxml trees. Unsupported or invalid files fall back to
        the legacy structural heuristics.
        """
        structures = []
        target_paths = set(file_paths) if file_paths else None
        js_ast_candidates = []

        for file_info in self.files:
            if target_paths is not None and file_info['path'] not in target_paths:
                continue

            ext = os.path.splitext(file_info['path'])[1].lower()
            content = file_info.get('content', '')
            if not content:
                continue

            lines = content.split('\n')
            file_structures = []

            if ext == '.py':
                file_structures.extend(self._extract_python_ast_structures(file_info, content))

            elif ext in self.JS_AST_EXTENSIONS:
                js_ast_candidates.append(file_info)
                if ext in {'.jsx', '.tsx'}:
                    file_structures.extend(self._extract_markup_structures(file_info, content))

            elif ext in self.HTML_AST_EXTENSIONS:
                file_structures.extend(self._extract_markup_ast_structures(file_info, content, parser_kind='html'))

            elif ext in self.XML_AST_EXTENSIONS:
                file_structures.extend(self._extract_markup_ast_structures(file_info, content, parser_kind='xml'))

            elif ext in self.CSS_STRUCTURE_EXTENSIONS:
                file_structures.extend(self._extract_css_structures(file_info, content))

            else:
                if ext in self.BRACE_STYLE_EXTENSIONS:
                    file_structures.extend(self._extract_brace_structures(file_info, lines))

                if ext in self.END_STYLE_EXTENSIONS:
                    file_structures.extend(self._extract_end_delimited_structures(file_info, lines))

                if ext in self.MARKUP_EXTENSIONS:
                    file_structures.extend(self._extract_markup_structures(file_info, content))

            structures.extend(self._dedupe_structures(file_structures))

        if js_ast_candidates:
            js_structures = self._extract_js_ast_structures(js_ast_candidates)
            structures.extend(self._dedupe_structures(js_structures))

        return self._dedupe_structures(structures)

    def _build_structure_id(self, file_info, parser_name, path_segments):
        """Builds a stable identifier for a detected structure."""
        normalized_rel_path = (file_info.get('rel_path') or file_info.get('path') or '').replace(os.sep, '/')
        joined_segments = "/".join(path_segments)
        return f"{parser_name}:{normalized_rel_path}::{joined_segments}"

    def _build_structure(
        self,
        file_info,
        name,
        structure_type,
        start_line,
        end_line,
        lines,
        display_name=None,
        structure_id=None,
        parser_name=None,
        header_text=None
    ):
        """Builds the normalized structure payload for the UI."""
        start_line = max(int(start_line), 1)
        end_line = max(int(end_line), start_line)
        snippet = '\n'.join(lines[start_line - 1:end_line])
        line_count = max(end_line - start_line + 1, 1)
        return {
            'name': name,
            'display_name': display_name or name,
            'type': structure_type,
            'content': snippet,
            'header': header_text or '',
            'file_rel_path': file_info['rel_path'],
            'path': f"{file_info['path']}:{start_line}",
            'start_line': start_line,
            'line_count': line_count,
            'structure_id': structure_id,
            'parser': parser_name or 'heuristic',
        }

    def _dedupe_structures(self, items):
        """Removes duplicated structures produced by overlapping parsers/heuristics."""
        ordered = []
        seen = set()

        for item in items:
            structure_id = item.get('structure_id')
            if structure_id:
                key = structure_id
            else:
                key = (
                    item.get('file_rel_path'),
                    item.get('type'),
                    item.get('name'),
                    item.get('start_line'),
                    item.get('line_count')
                )
            if key in seen:
                continue
            seen.add(key)
            ordered.append(item)

        return ordered

    def _next_structure_segment(self, counters, structure_type, name):
        """Allocates a stable sibling segment for a structure path."""
        base = f"{structure_type}:{name or 'anonymous'}"
        index = counters.get(base, 0)
        counters[base] = index + 1
        return f"{base}[{index}]"

    def _extract_python_ast_structures(self, file_info, content):
        """Extracts Python structures from the built-in AST."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._extract_python_structures(file_info, content.split('\n'))

        lines = content.split('\n')
        results = []

        def visit_statement_list(statements, parent_path, inside_class=False):
            sibling_counters = {}

            for statement in statements:
                if isinstance(statement, ast.ClassDef):
                    segment = self._next_structure_segment(sibling_counters, 'class', statement.name)
                    current_path = parent_path + [segment]
                    structure_id = self._build_structure_id(file_info, 'python-ast', current_path)
                    end_line = getattr(statement, 'end_lineno', statement.lineno)
                    results.append(
                        self._build_structure(
                            file_info,
                            name=statement.name,
                            structure_type='class',
                            start_line=statement.lineno,
                            end_line=end_line,
                            lines=lines,
                            display_name=statement.name,
                            structure_id=structure_id,
                            parser_name='python-ast'
                        )
                    )
                    visit_statement_list(statement.body, current_path, inside_class=True)
                    continue

                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    structure_type = 'method' if inside_class else 'function'
                    segment = self._next_structure_segment(sibling_counters, structure_type, statement.name)
                    current_path = parent_path + [segment]
                    structure_id = self._build_structure_id(file_info, 'python-ast', current_path)
                    end_line = getattr(statement, 'end_lineno', statement.lineno)
                    results.append(
                        self._build_structure(
                            file_info,
                            name=statement.name,
                            structure_type=structure_type,
                            start_line=statement.lineno,
                            end_line=end_line,
                            lines=lines,
                            display_name=f"{statement.name}()",
                            structure_id=structure_id,
                            parser_name='python-ast'
                        )
                    )
                    visit_statement_list(statement.body, current_path, inside_class=False)
                    continue

                for nested_body in self._iter_python_nested_bodies(statement):
                    visit_statement_list(nested_body, parent_path, inside_class=inside_class)

        visit_statement_list(getattr(tree, 'body', []), [], inside_class=False)
        return results

    def _iter_python_nested_bodies(self, statement):
        """Returns child statement lists that may contain nested Python declarations."""
        body_attributes = ['body', 'orelse', 'finalbody']

        if isinstance(statement, ast.Try):
            for attr in body_attributes:
                nested = getattr(statement, attr, None)
                if nested:
                    yield nested
            for handler in getattr(statement, 'handlers', []):
                if getattr(handler, 'body', None):
                    yield handler.body
            return

        for attr in body_attributes:
            nested = getattr(statement, attr, None)
            if nested:
                yield nested

    def _extract_js_ast_structures(self, file_infos):
        """Extracts JS/TS/JSX/TSX structures through the bundled Node AST helper."""
        if not file_infos:
            return []
        if not os.path.isfile(self.JS_AST_HELPER_PATH):
            return []

        payload = [
            {
                'path': file_info['path'],
                'rel_path': file_info['rel_path'],
                'ext': os.path.splitext(file_info['path'])[1].lower(),
                'content': file_info.get('content', ''),
            }
            for file_info in file_infos
        ]

        try:
            completed = subprocess.run(
                ['node', self.JS_AST_HELPER_PATH],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=False
            )
        except Exception as exc:
            print(f"ProjectManager: Error running JS AST helper: {exc}")
            return self._extract_js_ast_structures_fallback(file_infos)

        if completed.returncode != 0:
            print(f"ProjectManager: JS AST helper failed: {completed.stderr.strip()}")
            return self._extract_js_ast_structures_fallback(file_infos)

        try:
            parsed = json.loads(completed.stdout or '{}')
        except json.JSONDecodeError as exc:
            print(f"ProjectManager: Invalid JS AST helper output: {exc}")
            return self._extract_js_ast_structures_fallback(file_infos)

        structures_by_path = parsed.get('structures', {})
        results = []

        for file_info in file_infos:
            content = file_info.get('content', '')
            lines = content.split('\n')
            extracted = structures_by_path.get(file_info['path'], [])

            if not extracted:
                results.extend(self._extract_js_ast_structures_fallback([file_info]))
                continue

            for item in extracted:
                start_line = item.get('start_line', 1)
                end_line = item.get('end_line', start_line)
                results.append(
                    self._build_structure(
                        file_info,
                        name=item.get('name', 'anonymous'),
                        structure_type=item.get('type', 'function'),
                        start_line=start_line,
                        end_line=end_line,
                        lines=lines,
                        display_name=item.get('display_name') or item.get('name', 'anonymous'),
                        structure_id=item.get('structure_id'),
                        parser_name=item.get('parser', 'javascript-ast'),
                        header_text=item.get('header', '')
                    )
                )

        return results

    def _extract_js_ast_structures_fallback(self, file_infos):
        """Falls back to the legacy JS-style heuristics when AST parsing is unavailable."""
        results = []
        for file_info in file_infos:
            content = file_info.get('content', '')
            ext = os.path.splitext(file_info['path'])[1].lower()
            file_structures = []
            lines = file_info.get('content', '').split('\n')
            file_structures.extend(self._extract_brace_structures(file_info, lines))
            if ext in {'.jsx', '.tsx'} and content:
                file_structures.extend(self._extract_react_visual_return_structures(file_info, content))
            results.extend(file_structures)
        return results

    def _extract_css_structures(self, file_info, content):
        """Extracts CSS-like rule blocks, at-rules, and nested steps from stylesheet files."""
        normalized = (content or '').replace('\r\n', '\n').replace('\r', '\n')
        if not normalized.strip():
            return []

        lines = normalized.split('\n')
        line_starts = [0]
        for index, char in enumerate(normalized):
            if char == '\n':
                line_starts.append(index + 1)

        def line_number_for_index(char_index):
            return max(bisect_right(line_starts, max(char_index, 0)), 1)

        results = []
        stack = []
        statement_start = 0
        interpolation_depth = 0
        in_single = False
        in_double = False
        in_line_comment = False
        in_block_comment = False
        escape = False
        index = 0

        while index < len(normalized):
            char = normalized[index]
            next_char = normalized[index + 1] if index + 1 < len(normalized) else ''

            if in_line_comment:
                if char == '\n':
                    in_line_comment = False
                index += 1
                continue

            if in_block_comment:
                if char == '*' and next_char == '/':
                    in_block_comment = False
                    index += 2
                    continue
                index += 1
                continue

            if in_single:
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == "'":
                    in_single = False
                index += 1
                continue

            if in_double:
                if escape:
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == '"':
                    in_double = False
                index += 1
                continue

            if char == '/' and next_char == '*':
                in_block_comment = True
                index += 2
                continue

            if char == '/' and next_char == '/':
                in_line_comment = True
                index += 2
                continue

            if char == "'":
                in_single = True
                index += 1
                continue

            if char == '"':
                in_double = True
                index += 1
                continue

            if interpolation_depth:
                if char == '{':
                    interpolation_depth += 1
                elif char == '}':
                    interpolation_depth = max(interpolation_depth - 1, 0)
                index += 1
                continue

            if (char == '#' or char == '@') and next_char == '{':
                interpolation_depth = 1
                index += 2
                continue

            if char == '{':
                raw_header, header_start_index = self._extract_css_header_segment(normalized, statement_start, index)
                normalized_header = self._normalize_css_header_text(raw_header)
                structure_type = self._classify_css_structure_header(normalized_header)

                block_info = {"structure_type": None}
                if structure_type:
                    header_with_open = f"{normalized_header} {{"
                    compact_name = " ".join(part.strip() for part in normalized_header.splitlines() if part.strip()) or normalized_header
                    block_info = {
                        "structure_type": structure_type,
                        "name": compact_name,
                        "display_name": compact_name,
                        "start_line": line_number_for_index(header_start_index),
                        "header": header_with_open,
                    }

                stack.append(block_info)
                statement_start = index + 1
                index += 1
                continue

            if char == ';':
                statement_start = index + 1
                index += 1
                continue

            if char == '}':
                if stack:
                    block_info = stack.pop()
                    if block_info.get("structure_type"):
                        results.append(
                            self._build_structure(
                                file_info,
                                name=block_info["name"],
                                structure_type=block_info["structure_type"],
                                start_line=block_info["start_line"],
                                end_line=line_number_for_index(index),
                                lines=lines,
                                display_name=block_info["display_name"],
                                parser_name='css-heuristic',
                                header_text=block_info["header"]
                            )
                        )
                statement_start = index + 1
                index += 1
                continue

            index += 1

        return results

    def _extract_css_header_segment(self, content, start_idx, end_idx):
        """Returns the raw CSS header text and the char index where it starts."""
        segment = content[max(start_idx, 0):max(end_idx, 0)]
        offset = 0

        while offset < len(segment):
            current = segment[offset:]
            whitespace_match = re.match(r'\s+', current)
            if whitespace_match:
                offset += whitespace_match.end()
                continue

            if current.startswith('/*'):
                comment_end = current.find('*/', 2)
                if comment_end == -1:
                    return "", max(start_idx + offset, 0)
                offset += comment_end + 2
                continue

            if current.startswith('//'):
                newline_index = current.find('\n', 2)
                if newline_index == -1:
                    return "", max(start_idx + offset, 0)
                offset += newline_index + 1
                continue

            break

        remaining = segment[offset:]
        leading_trim = len(remaining) - len(remaining.lstrip())
        header_start_index = max(start_idx + offset + leading_trim, 0)
        return remaining.strip(), header_start_index

    def _normalize_css_header_text(self, header_text):
        """Normalizes CSS headers by removing comment-only noise while preserving selector shape."""
        cleaned = re.sub(r'/\*.*?\*/', ' ', header_text or '', flags=re.DOTALL)
        lines = []
        for line in cleaned.split('\n'):
            stripped = re.sub(r'//.*$', '', line).strip()
            if stripped:
                lines.append(stripped)
        return '\n'.join(lines).strip()

    def _classify_css_structure_header(self, header_text):
        """Classifies a CSS-like header into a stored structure type."""
        cleaned = (header_text or '').strip()
        if not cleaned:
            return None

        if cleaned.startswith('@'):
            return 'css_at_rule'
        if self.CSS_KEYFRAME_STEP_RE.match(cleaned):
            return 'css_keyframe_step'
        if self.CSS_PROPERTY_GROUP_RE.match(cleaned):
            return 'css_property_group'
        if any(token in cleaned for token in ('.', '#', '[', ']', ':', '&', '>', '+', '~', '*', ',')):
            return 'css_rule'
        if self.CSS_ELEMENT_SELECTOR_RE.match(cleaned):
            return 'css_rule'
        return None

    def _extract_react_visual_return_structures(self, file_info, content):
        """Heuristically extracts React render returns when the JS AST helper cannot parse the file."""
        normalized = (content or '').replace('\r\n', '\n').replace('\r', '\n')
        if not normalized.strip():
            return []

        results = []
        lines = normalized.split('\n')

        for match in re.finditer(r'\breturn\b', normalized):
            statement_end = self._find_js_return_statement_end(normalized, match.start())
            snippet = normalized[match.start():statement_end].strip()
            if not snippet or not self._looks_like_react_visual_return(snippet):
                continue

            jsx_label = self._extract_react_return_label(snippet)
            normalized_name = re.sub(r'[^\w$.:-]+', '_', jsx_label.strip('<>')) or 'jsx'
            start_line = normalized.count('\n', 0, match.start()) + 1
            end_line = max(normalized.count('\n', 0, statement_end) + 1, start_line)

            results.append(
                self._build_structure(
                    file_info,
                    name=f"return_{normalized_name}",
                    structure_type='react_return',
                    start_line=start_line,
                    end_line=end_line,
                    lines=lines,
                    display_name=f"return ({jsx_label})",
                    header_text=f"return ({jsx_label})"
                )
            )

        return results

    def _find_js_return_statement_end(self, content, return_index):
        """Best-effort statement end finder for JS/TS return expressions."""
        idx = return_index
        text_length = len(content)
        paren_depth = 0
        bracket_depth = 0
        brace_depth = 0
        in_single = False
        in_double = False
        in_backtick = False
        escape = False

        while idx < text_length:
            char = content[idx]
            next_char = content[idx + 1] if idx + 1 < text_length else ''

            if escape:
                escape = False
                idx += 1
                continue

            if char == '\\' and (in_single or in_double or in_backtick):
                escape = True
                idx += 1
                continue

            if not in_single and not in_double and not in_backtick:
                if char == '/' and next_char == '/':
                    idx += 2
                    while idx < text_length and content[idx] != '\n':
                        idx += 1
                    continue
                if char == '/' and next_char == '*':
                    idx += 2
                    while idx + 1 < text_length and not (content[idx] == '*' and content[idx + 1] == '/'):
                        idx += 1
                    idx = min(idx + 2, text_length)
                    continue

            if char == "'" and not in_double and not in_backtick:
                in_single = not in_single
                idx += 1
                continue
            if char == '"' and not in_single and not in_backtick:
                in_double = not in_double
                idx += 1
                continue
            if char == '`' and not in_single and not in_double:
                in_backtick = not in_backtick
                idx += 1
                continue

            if in_single or in_double or in_backtick:
                idx += 1
                continue

            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth = max(paren_depth - 1, 0)
            elif char == '[':
                bracket_depth += 1
            elif char == ']':
                bracket_depth = max(bracket_depth - 1, 0)
            elif char == '{':
                brace_depth += 1
            elif char == '}':
                if paren_depth == 0 and bracket_depth == 0 and brace_depth == 0:
                    return idx
                brace_depth = max(brace_depth - 1, 0)
            elif char == ';' and paren_depth == 0 and bracket_depth == 0 and brace_depth == 0:
                return idx + 1

            idx += 1

        return text_length

    def _looks_like_react_visual_return(self, snippet):
        """Returns True when a return statement appears to yield JSX visual output."""
        if not snippet:
            return False
        body = re.sub(r'^\s*return\b', '', snippet, flags=re.IGNORECASE).strip()
        if not body:
            return False
        return bool(re.search(r'(^|[?:(=,\[]\s*)<(?:[A-Za-z_][\w:.$-]*|>)', body, re.DOTALL))

    def _extract_react_return_label(self, snippet):
        """Extracts a compact JSX label for a visual return."""
        if not snippet:
            return '<jsx>'
        body = re.sub(r'^\s*return\b', '', snippet, flags=re.IGNORECASE).strip()
        match = re.search(r'<\s*(>|[A-Za-z_][\w:.$-]*)', body)
        if not match:
            return '<jsx>'
        tag_name = match.group(1)
        if tag_name == '>':
            return '<>'
        return f'<{tag_name}>'

    def _extract_markup_ast_structures(self, file_info, content, parser_kind='html'):
        """Extracts markup nodes from an lxml element tree."""
        lines = content.split('\n')

        try:
            if parser_kind == 'xml':
                parser = etree.XMLParser(recover=True, remove_comments=False)
                try:
                    root = etree.fromstring(content.encode('utf-8'), parser=parser)
                    wrapper_children = [root]
                except etree.XMLSyntaxError:
                    wrapped = f"<ast_root>\n{content}\n</ast_root>"
                    root = etree.fromstring(wrapped.encode('utf-8'), parser=parser)
                    wrapper_children = list(root)
            else:
                parser = html.HTMLParser(remove_comments=False, recover=True)
                root = html.fragment_fromstring(content, create_parent='ast_root', parser=parser)
                wrapper_children = list(root)
        except Exception:
            return self._extract_markup_structures(file_info, content)

        results = []

        def walk_elements(elements, parent_path):
            sibling_counters = {}

            for element in elements:
                if not isinstance(getattr(element, 'tag', None), str):
                    walk_elements(list(element), parent_path)
                    continue

                tag_name = element.tag
                start_line = int(getattr(element, 'sourceline', 1) or 1)
                serialized = etree.tostring(element, encoding='unicode', with_tail=False) or ''
                estimated_lines = max(serialized.count('\n') + 1, 1)
                end_line = max(start_line + estimated_lines - 1, start_line)
                segment = self._next_structure_segment(sibling_counters, 'tag', tag_name)
                current_path = parent_path + [segment]
                structure_id = self._build_structure_id(file_info, f'{parser_kind}-ast', current_path)
                results.append(
                    self._build_structure(
                        file_info,
                        name=tag_name,
                        structure_type='tag',
                        start_line=start_line,
                        end_line=end_line,
                        lines=lines,
                        display_name=f"<{tag_name}>",
                        structure_id=structure_id,
                        parser_name=f'{parser_kind}-ast'
                    )
                )
                walk_elements(list(element), current_path)

        walk_elements(wrapper_children, [])
        return results

    def _extract_python_structures(self, file_info, lines):
        results = []
        pattern = re.compile(r'^([ \t]*)(?:(async)\s+)?(def|class)\s+([a-zA-Z_]\w*)\b')

        i = 0
        while i < len(lines):
            line = lines[i]
            match = pattern.match(line)
            if not match:
                i += 1
                continue

            indent = match.group(1)
            kind = match.group(3)
            name = match.group(4)
            start_idx = i
            end_idx = i + 1

            while end_idx < len(lines):
                next_line = lines[end_idx]
                stripped = next_line.strip()
                if not stripped or stripped.startswith('#'):
                    end_idx += 1
                    continue

                next_indent = re.match(r'^([ \t]*)', next_line).group(1)
                if len(next_indent) <= len(indent):
                    break
                end_idx += 1

            while end_idx > start_idx + 1 and not lines[end_idx - 1].strip():
                end_idx -= 1

            display_name = f"{name}()" if kind == 'def' else name
            structure_type = 'function' if kind == 'def' else 'class'
            results.append(
                self._build_structure(
                    file_info,
                    name=name,
                    structure_type=structure_type,
                    start_line=start_idx + 1,
                    end_line=end_idx,
                    lines=lines,
                    display_name=display_name
                )
            )
            i += 1

        return results

    def _extract_brace_structures(self, file_info, lines):
        results = []
        patterns = [
            ('function', re.compile(r'^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][\w$]*)\s*\(')),
            ('function', re.compile(r'^\s*function\s+([A-Za-z_][\w$-]*)\s*(?:\(\))?\s*\{')),
            ('function', re.compile(r'^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_][\w$]*)\s*\(')),
            ('function', re.compile(r'^\s*fn\s+([A-Za-z_][\w$]*)\s*\(')),
            ('function', re.compile(r'^\s*fun\s+([A-Za-z_][\w$]*)\s*\(')),
            ('function', re.compile(r'^\s*(?:sub|proc(?:edure)?)\s+([A-Za-z_][\w$]*)\b')),
            ('function', re.compile(r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][\w$]*)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[A-Za-z_][\w$]*)\s*=>')),
            ('class', re.compile(r'^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_][\w$]*)\b')),
            ('interface', re.compile(r'^\s*(?:export\s+)?interface\s+([A-Za-z_][\w$]*)\b')),
            ('struct', re.compile(r'^\s*(?:export\s+)?struct\s+([A-Za-z_][\w$]*)\b')),
            ('enum', re.compile(r'^\s*(?:export\s+)?enum\s+([A-Za-z_][\w$]*)\b')),
            ('namespace', re.compile(r'^\s*(?:export\s+)?(?:namespace|module)\s+([A-Za-z_][\w$.:-]*)\b')),
            ('method', re.compile(r'^\s*(?:public|private|protected|internal|static|final|virtual|override|abstract|async|get|set|readonly|sealed|\s)*(?:[A-Za-z_][\w$<>\[\],?*&:.]+\s+)*([A-Za-z_~][\w$]*)\s*\([^;=]*\)\s*(?:const\s*)?(?:\{|=>)')),
            ('method', re.compile(r'^\s*(?:async\s+)?([A-Za-z_][\w$]*)\s*\([^;=]*\)\s*\{')),
        ]
        ignored_names = {
            'if', 'for', 'while', 'switch', 'catch', 'foreach', 'with', 'return',
            'else', 'do', 'try', 'finally', 'case'
        }

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            for structure_type, pattern in patterns:
                match = pattern.match(line)
                if not match:
                    continue

                name = match.group(1)
                if not name or name.lower() in ignored_names:
                    continue

                end_line = self._find_brace_block_end(lines, idx)
                if end_line is None:
                    continue

                display_name = f"{name}()" if structure_type in {'function', 'method'} else name
                results.append(
                    self._build_structure(
                        file_info,
                        name=name,
                        structure_type=structure_type,
                        start_line=idx + 1,
                        end_line=end_line,
                        lines=lines,
                        display_name=display_name
                    )
                )
                break

        return results

    def _find_brace_block_end(self, lines, start_idx, max_signature_lines=8):
        """Finds the end line for a structure delimited by braces."""
        search_end = min(len(lines), start_idx + max_signature_lines)
        brace_start = None

        for line_idx in range(start_idx, search_end):
            if '{' in lines[line_idx]:
                brace_start = line_idx
                break

        if brace_start is None:
            return None

        depth = 0
        opened = False
        in_single = False
        in_double = False
        in_backtick = False
        escape = False

        for line_idx in range(brace_start, len(lines)):
            for ch in lines[line_idx]:
                if escape:
                    escape = False
                    continue

                if ch == '\\' and (in_single or in_double or in_backtick):
                    escape = True
                    continue

                if ch == "'" and not in_double and not in_backtick:
                    in_single = not in_single
                    continue
                if ch == '"' and not in_single and not in_backtick:
                    in_double = not in_double
                    continue
                if ch == '`' and not in_single and not in_double:
                    in_backtick = not in_backtick
                    continue

                if in_single or in_double or in_backtick:
                    continue

                if ch == '{':
                    depth += 1
                    opened = True
                elif ch == '}':
                    depth -= 1
                    if opened and depth <= 0:
                        return line_idx + 1

        return None

    def _extract_end_delimited_structures(self, file_info, lines):
        results = []
        patterns = [
            ('function', re.compile(r'^\s*(?:def|defp|defmacro|defmacrop)\s+([A-Za-z_][\w!?=]*)\b')),
            ('module', re.compile(r'^\s*defmodule\s+([A-Za-z_][\w.]+)\b')),
            ('function', re.compile(r'^\s*(?:local\s+)?function\s+([A-Za-z_][\w.:]*)\s*\(')),
            ('class', re.compile(r'^\s*(?:class|module)\s+([A-Za-z_][\w.:]*)\b')),
        ]

        for idx, line in enumerate(lines):
            if not line.strip():
                continue

            for structure_type, pattern in patterns:
                match = pattern.match(line)
                if not match:
                    continue

                name = match.group(1)
                end_line = self._find_end_keyword_block(lines, idx)
                if end_line is None:
                    continue

                display_name = f"{name}()" if structure_type == 'function' else name
                results.append(
                    self._build_structure(
                        file_info,
                        name=name,
                        structure_type=structure_type,
                        start_line=idx + 1,
                        end_line=end_line,
                        lines=lines,
                        display_name=display_name
                    )
                )
                break

        return results

    def _find_end_keyword_block(self, lines, start_idx):
        """Finds the end line for languages that close blocks with 'end'."""
        open_pattern = re.compile(r'\b(?:def|defp|defmacro|defmacrop|defmodule|class|module|function|if|unless|case|begin|while|until|for|try|receive|fn)\b')
        close_pattern = re.compile(r'\bend\b')
        depth = 0

        for line_idx in range(start_idx, len(lines)):
            stripped = lines[line_idx].strip()
            if not stripped or stripped.startswith('#') or stripped.startswith('--'):
                continue

            depth += len(open_pattern.findall(stripped))
            depth -= len(close_pattern.findall(stripped))

            if line_idx > start_idx and depth <= 0:
                return line_idx + 1

        return None

    def _extract_markup_structures(self, file_info, content):
        results = []
        lines = content.split('\n')
        tag_pattern = re.compile(r'<!--.*?-->|<!\[CDATA\[.*?\]\]>|<\?.*?\?>|</?\s*([A-Za-z][\w:.-]*)\b[^<>]*?/?>', re.DOTALL)
        void_tags = {
            'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
            'link', 'meta', 'param', 'source', 'track', 'wbr'
        }
        stack = []

        for match in tag_pattern.finditer(content):
            token = match.group(0)
            tag_name = match.group(1)
            if not tag_name:
                continue

            tag_name = tag_name.strip()
            lower_name = tag_name.lower()
            if lower_name in void_tags:
                continue

            is_closing = token.lstrip().startswith('</')
            is_self_closing = token.rstrip().endswith('/>')
            line_number = content.count('\n', 0, match.start()) + 1

            if is_self_closing:
                continue

            if not is_closing:
                stack.append((tag_name, line_number))
                continue

            for stack_idx in range(len(stack) - 1, -1, -1):
                open_name, open_line = stack[stack_idx]
                if open_name.lower() != lower_name:
                    continue

                del stack[stack_idx:]
                results.append(
                    self._build_structure(
                        file_info,
                        name=tag_name,
                        structure_type='tag',
                        start_line=open_line,
                        end_line=line_number,
                        lines=lines,
                        display_name=f"<{tag_name}>"
                    )
                )
                break

        return results
