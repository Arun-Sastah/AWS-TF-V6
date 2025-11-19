import os

IGNORE_FOLDERS = {
    'node_modules', 'venv', '__pycache__', 'build', 'dist', '.git', '.idea',
    '.vscode', '.next', '.turbo', 'coverage', '.pytest_cache'
}

def list_structure(startpath):
    for root, dirs, files in os.walk(startpath):
        # Ignore unwanted directories
        dirs[:] = [d for d in dirs if d not in IGNORE_FOLDERS]

        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * level
        print(f'{indent}{os.path.basename(root)}/')

        subindent = ' ' * 4 * (level + 1)
        for f in files:
            # Ignore hidden/system files
            if not f.startswith('.') and not f.endswith('.pyc'):
                print(f'{subindent}{f}')

list_structure(".")
