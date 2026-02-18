import os
import re

class ProjectManager:
    """
    Manages the loading and scanning of project files.
    """
    
    # Supported code extensions
    CODE_EXTENSIONS = {
        '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', 
        '.java', '.cpp', '.c', '.h', '.cs', '.go', '.rs', '.php',
        '.rb', '.swift', '.kt', '.sql', '.json', '.xml', '.yml', '.yaml'
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
            if any(part.startswith('.') or part in ('__pycache__', 'node_modules', 'venv', 'env') for part in root.split(os.sep)):
                continue
                
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.CODE_EXTENSIONS:
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

    def get_directory_tree(self):
        """
        Generates a text representation of the project's directory tree.
        Respects the same ignore rules as _scan_directory.
        """
        if not self.current_project_path:
            return ""
        
        IGNORE_DIRS = {'.git', '__pycache__', 'node_modules', 'venv', 'env', '.idea', '.vscode', '.next', 'dist', 'build'}
        lines = [os.path.basename(self.current_project_path) + "/"]
        
        def _build_tree(dir_path, prefix=""):
            try:
                entries = sorted(os.listdir(dir_path))
            except PermissionError:
                return
            
            # Filter out hidden and ignored directories/files
            dirs = []
            files = []
            for entry in entries:
                if entry.startswith('.') and entry not in ('.env',):
                    continue
                full_path = os.path.join(dir_path, entry)
                if os.path.isdir(full_path):
                    if entry not in IGNORE_DIRS:
                        dirs.append(entry)
                else:
                    files.append(entry)
            
            all_entries = dirs + files
            for i, entry in enumerate(all_entries):
                is_last = (i == len(all_entries) - 1)
                connector = "└── " if is_last else "├── "
                full_path = os.path.join(dir_path, entry)
                
                if os.path.isdir(full_path):
                    lines.append(f"{prefix}{connector}{entry}/")
                    extension = "    " if is_last else "│   "
                    _build_tree(full_path, prefix + extension)
                else:
                    lines.append(f"{prefix}{connector}{entry}")
        
        _build_tree(self.current_project_path)
        return "\n".join(lines)

    def find_relevant_files(self, user_query, relevant_files_subset=None):
        """
        Finds files that are most relevant to the user_query.
        This is a simple heuristic based on keyword overlap.
        
        Args:
            user_query: The user's text description.
            relevant_files_subset: Optional list of file dicts to search within. 
                                   If None, searches all project files.
        
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
            
            if score > 0:
                scored_files.append((score, file))

        # Sort by score descending
        scored_files.sort(key=lambda x: x[0], reverse=True)
        
        # Return just the file objects
        return [f[1] for f in scored_files]

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
        IGNORE_DIRS = {'.git', '__pycache__', 'node_modules', 'venv', 'env',
                       '.idea', '.vscode', '.next', 'dist', 'build'}

        for root, dirs, filenames in os.walk(self.current_project_path):
            # Filter dirs in-place to skip ignored
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]

            for filename in filenames:
                if filename.startswith('.'):
                    continue
                ext = os.path.splitext(filename)[1].lower()
                if ext not in self.CODE_EXTENSIONS:
                    full_path = os.path.join(root, filename)
                    non_code.append({
                        'path': full_path,
                        'rel_path': os.path.relpath(full_path, self.current_project_path)
                    })

        return non_code

    def extract_functions(self):
        """
        Extracts all function definitions from loaded code files.
        Returns a list of dicts: {
            'name': str,
            'type': 'function',
            'content': str,
            'file_rel_path': str,
            'path': str (formatted for UI: "file:line")
        }
        """
        functions = []
        for f in self.files:
            ext = os.path.splitext(f['path'])[1].lower()
            content = f['content']
            lines = content.split('\n')
            
            if ext == '.py':
                functions.extend(self._extract_python_functions(f, lines))
            elif ext in ('.js', '.jsx', '.ts', '.tsx'):
                functions.extend(self._extract_js_functions(f, content, lines))
                
        return functions

    def _extract_python_functions(self, file_info, lines):
        results = []
        # Regex for Python function/method definitions
        # Groups: 1: indentation, 2: 'async ' (optional), 3: 'def ', 4: function name
        py_fn_pattern = re.compile(r'^([ \t]*)((?:async\s+)?def\s+)([a-zA-Z_]\w*)\s*\(')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            match = py_fn_pattern.match(line)
            if match:
                indent = match.group(1)
                fn_name = match.group(3)
                start_line = i
                
                # Find the end of the function (until next line with same or less indentation, excluding empty/comment lines)
                end_line = i + 1
                while end_line < len(lines):
                    next_line = lines[end_line]
                    if not next_line.strip() or next_line.strip().startswith('#'):
                        end_line += 1
                        continue
                        
                    next_indent_match = re.match(r'^([ \t]*)', next_line)
                    next_indent = next_indent_match.group(1) if next_indent_match else ""
                    
                    if len(next_indent) <= len(indent):
                        break
                    end_line += 1
                
                # Cleanup trailing whitespace/empty lines
                while end_line > start_line + 1 and not lines[end_line - 1].strip():
                    end_line -= 1
                    
                fn_content = '\n'.join(lines[start_line:end_line])
                results.append({
                    'name': fn_name,
                    'type': 'function',
                    'content': fn_content,
                    'file_rel_path': file_info['rel_path'],
                    'path': f"{file_info['path']}:{start_line+1}"
                })
                i = end_line - 1
            i += 1
        return results

    def _extract_js_functions(self, file_info, content, lines):
        results = []
        # Basic regex to find starts of functions
        # This is a heuristic and might miss some complex cases, but covers most common ones
        
        # 1. function keyword: function name(...) {
        js_fn_keyword = re.compile(r'(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z_]\w*)\s*\(')
        # 2. Arrow functions assigned to const/let/var: const name = (...) => {
        js_arrow_fn = re.compile(r'(?:export\s+)?(?:const|let|var)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>')
        # 3. Method definitions in objects/classes: name(...) {
        js_method = re.compile(r'^[ \t]*([a-zA-Z_]\w*)\s*\([^)]*\)\s*\{')

        for i, line in enumerate(lines):
            name = None
            match = js_fn_keyword.search(line) or js_arrow_fn.search(line) or js_method.match(line)
            
            if match:
                name = match.group(1)
                start_line = i
                
                # For JS, extracting the full body is harder because of nesting.
                # We'll use a simple brace counting heuristic starting from the first '{' found
                # Or if it's an arrow function without braces (single expression), it's just that line (or until ;)
                
                start_idx = content.find(line)
                # Find the first '{'
                brace_start = content.find('{', start_idx)
                
                if brace_start != -1 and (brace_start < content.find('\n', start_idx + len(line)) or '\n' not in line):
                    # Brace counting
                    count = 1
                    current_idx = brace_start + 1
                    while count > 0 and current_idx < len(content):
                        char = content[current_idx]
                        if char == '{':
                            count += 1
                        elif char == '}':
                            count -= 1
                        current_idx += 1
                    
                    fn_content = content[start_idx:current_idx]
                    results.append({
                        'name': name,
                        'type': 'function',
                        'content': fn_content,
                        'file_rel_path': file_info['rel_path'],
                        'path': f"{file_info['path']}:{start_line+1}"
                    })
                else:
                    # Likely single line arrow function or we missed the brace
                    # Just take the line for now as a fallback
                    results.append({
                        'name': name,
                        'type': 'function',
                        'content': line.strip(),
                        'file_rel_path': file_info['rel_path'],
                        'path': f"{file_info['path']}:{start_line+1}"
                    })
        return results
