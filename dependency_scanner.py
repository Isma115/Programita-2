import os
import re
import ast
import sys
import tkinter as tk
from tkinter import filedialog

def select_file():
    """Opens a file dialog to select a python file."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    file_path = filedialog.askopenfilename(
        title="Selecciona un fichero de código para analizar",
        filetypes=[("Archivos de Python", "*.py"), ("Todos los archivos", "*.*")]
    )
    return file_path

def find_imports(file_path):
    """Parses a Python file to find imports using AST."""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
    except Exception as e:
        print(f"Error al analizar imports en {file_path}: {e}")
    return imports

def find_file_references(file_path):
    """Scans a file for strings that look like file paths."""
    references = set()
    # Regex for potential file paths: looking for strings ending in common code extensions
    # This is a heuristic and might produce false positives
    path_pattern = re.compile(r'[\'"]([^\'"\n\r]+\.(?:py|js|jsx|html|css|json|txt|md))[\'"]')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            matches = path_pattern.findall(content)
            for match in matches:
                references.add(match)
    except Exception as e:
        print(f"Error al buscar referencias de archivo en {file_path}: {e}")
    return references

def resolve_path(base_file, ref):
    """Attempts to resolve a reference to an absolute path."""
    base_dir = os.path.dirname(os.path.abspath(base_file))
    
    # Check if it's already an absolute path
    if os.path.isabs(ref):
        if os.path.exists(ref):
            return ref
    
    # Check relative to the file
    rel_path = os.path.join(base_dir, ref)
    if os.path.exists(rel_path):
        return rel_path
    
    # Check relative to the project root (assuming src structure or similar)
    # This is a bit of a guess, trying to go up directories
    current_dir = base_dir
    for _ in range(3): # Try going up 3 levels
        current_dir = os.path.dirname(current_dir)
        rel_path_root = os.path.join(current_dir, ref)
        if os.path.exists(rel_path_root):
            return rel_path_root
            
    return None

def main():
    print("Abriendo selector de archivos...")
    if len(sys.argv) > 1:
        selected_file = sys.argv[1]
    else:
        selected_file = select_file()
    
    if not selected_file:
        print("No se seleccionó ningún archivo.")
        return

    print(f"\nAnalizando: {selected_file}")
    print("-" * 50)
    
    # 1. Imports (Python specific)
    print("\n[IMPORTS DETECTADOS]")
    if selected_file.endswith('.py'):
        imports = find_imports(selected_file)
        if imports:
            for imp in sorted(imports):
                print(f"  - {imp}")
        else:
            print("  No se encontraron imports explícitos.")
    else:
        print("  El análisis de imports AST solo está disponible para archivos .py")

    # 2. String References (File paths)
    print("\n[OFERENCIAS A FICHEROS (Cadenas de texto)]")
    references = find_file_references(selected_file)
    if references:
        for ref in sorted(references):
            resolved = resolve_path(selected_file, ref)
            status = f"(Existe: {resolved})" if resolved else "(No encontrado o referencia abstracta)"
            print(f"  - {ref}  -->  {status}")
    else:
        print("  No se encontraron cadenas que parezcan nombres de archivo.")

    print("\n" + "-" * 50)
    print("Análisis completado.")
    input("\nPresiona ENTER para salir...")

if __name__ == "__main__":
    main()
