"""
Addon: Copia de Código
Creates a complete copy of the project maintaining directory structure,
but only including code files (based on file extensions).
"""
import os
import shutil
from datetime import datetime
from tkinter import filedialog, messagebox

from src.logic.project_manager import ProjectManager


# Documentation/context files previously copied by this addon. The source-code
# detection itself lives in ProjectManager to avoid maintaining two extension lists.
EXTRA_CONTEXT_EXTENSIONS = {
    '.md', '.markdown', '.mdown', '.rst', '.adoc',
}

# Directories to exclude from copying
EXCLUDED_DIRS = {
    '__pycache__', 
    '.git', 
    '.svn', 
    '.hg',
    'node_modules', 
    'venv', 
    '.venv', 
    'env',
    '.env',
    '.idea', 
    '.vscode',
    'dist', 
    'build', 
    '.next',
    'coverage',
    '.pytest_cache',
    '.mypy_cache',
    'egg-info',
    '.tox',
}


def run(app, args):
    """
    Creates a code-only copy of the project.
    
    Usage: copia de codigo [destino]
    
    If no destination is provided, a folder dialog will open.
    """
    # Get the project root directory
    if hasattr(app, 'controller') and hasattr(app.controller, 'project_manager'):
        pm = app.controller.project_manager
        project_path = pm.current_project_path
        project_name = os.path.basename(project_path) if project_path else "proyecto"
    else:
        return "Error: No se pudo obtener la ruta del proyecto actual."
    
    if not project_path or not os.path.isdir(project_path):
        return "Error: No hay un proyecto válido cargado."
    
    # Determine destination
    if args:
        dest_base = " ".join(args)
    else:
        # Open folder selection dialog
        dest_base = filedialog.askdirectory(
            title="Seleccionar carpeta destino para la copia de código",
            initialdir=os.path.expanduser("~")
        )
        
    if not dest_base:
        return "Operación cancelada."
    
    # Create destination folder with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_folder_name = f"{project_name}_codigo_{timestamp}"
    dest_path = os.path.join(dest_base, dest_folder_name)
    
    try:
        # Stats
        files_copied = 0
        dirs_created = 0
        
        # Walk through the project
        for root, dirs, files in os.walk(project_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith('.')]
            
            # Calculate relative path from project root
            rel_path = os.path.relpath(root, project_path)
            
            # Filter code files
            code_files = [f for f in files if _is_code_file(f)]
            
            if code_files or dirs:
                # Create directory in destination if needed
                if rel_path == '.':
                    dest_dir = dest_path
                else:
                    dest_dir = os.path.join(dest_path, rel_path)
                
                if code_files:  # Only create dir if it will contain files
                    os.makedirs(dest_dir, exist_ok=True)
                    dirs_created += 1
                    
                    # Copy code files
                    for file in code_files:
                        src_file = os.path.join(root, file)
                        dst_file = os.path.join(dest_dir, file)
                        shutil.copy2(src_file, dst_file)
                        files_copied += 1
        
        # Show success message
        result_msg = f"Copia de código completada:\n"
        result_msg += f"   Destino: {dest_path}\n"
        result_msg += f"   Archivos copiados: {files_copied}\n"
        result_msg += f"   Directorios creados: {dirs_created}"
        
        messagebox.showinfo(
            "Copia de Código",
            f"Copia completada exitosamente.\n\n"
            f"Destino: {dest_path}\n"
            f"Archivos copiados: {files_copied}\n"
            f"Directorios creados: {dirs_created}"
        )
        
        return result_msg
        
    except PermissionError:
        return f"Error: No se tienen permisos para escribir en '{dest_base}'."
    except Exception as e:
        return f"Error durante la copia: {str(e)}"


def _is_code_file(filename: str) -> bool:
    """
    Checks if a file is a code or relevant project-context file.
    """
    _, ext = os.path.splitext(filename)
    return ProjectManager.is_code_file(filename) or ext.lower() in EXTRA_CONTEXT_EXTENSIONS
