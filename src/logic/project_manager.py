import os
import re

class ProjectManager:
    """
    Manages the loading and scanning of project files.
    """
    IGNORED_DIRECTORIES = {
        '.git', '__pycache__', 'node_modules', 'venv', 'env',
        '.idea', '.vscode', '.next', 'dist', 'build'
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
        Extracts code structures from loaded files using broad heuristics.
        The result includes functions, methods, classes, modules and markup tags.
        """
        structures = []
        target_paths = set(file_paths) if file_paths else None

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
                file_structures.extend(self._extract_python_structures(file_info, lines))

            if ext in self.BRACE_STYLE_EXTENSIONS:
                file_structures.extend(self._extract_brace_structures(file_info, lines))

            if ext in self.END_STYLE_EXTENSIONS:
                file_structures.extend(self._extract_end_delimited_structures(file_info, lines))

            if ext in self.MARKUP_EXTENSIONS:
                file_structures.extend(self._extract_markup_structures(file_info, content))

            structures.extend(self._dedupe_structures(file_structures))

        return structures

    def _build_structure(self, file_info, name, structure_type, start_line, end_line, lines, display_name=None):
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
            'file_rel_path': file_info['rel_path'],
            'path': f"{file_info['path']}:{start_line}",
            'start_line': start_line,
            'line_count': line_count
        }

    def _dedupe_structures(self, items):
        """Removes duplicated structures produced by overlapping heuristics."""
        ordered = []
        seen = set()

        for item in items:
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
