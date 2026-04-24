import ast
import os

files = [
    'lirox/main.py',
    'lirox/config.py',
    'lirox/core/diagnostics.py',
    'lirox/core/backup.py',
    'lirox/learning/exporter.py',
    'lirox/learning/importer.py',
    'lirox/orchestrator/master.py',
    'lirox/core/__init__.py',
    'lirox/learning/__init__.py',
    'lirox/ui/display.py',
]

ok = True
for f in files:
    try:
        with open(f, 'r') as fh:
            ast.parse(fh.read(), filename=f)
        print(f'  OK: {f}')
    except SyntaxError as e:
        print(f'  ERR: {f}:{e.lineno} - {e.msg}')
        ok = False

print()
if ok:
    print('All files passed syntax check!')
else:
    print('SYNTAX ERRORS FOUND!')
