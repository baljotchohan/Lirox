import os
import ast

def check_directory(directory):
    issues = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        source = f.read()
                    ast.parse(source, filename=path)
                except SyntaxError as e:
                    issues.append(f"SyntaxError in {path}:{e.lineno} - {e.msg}")
                except Exception as e:
                    issues.append(f"Error reading {path}: {e}")
    return issues

if __name__ == '__main__':
    issues = check_directory('.')
    if issues:
        print("Found issues:")
        for issue in issues:
            print(issue)
    else:
        print("No syntax errors found.")
