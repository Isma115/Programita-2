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
