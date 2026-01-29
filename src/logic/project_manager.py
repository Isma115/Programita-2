import os

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

    def __init__(self):
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
