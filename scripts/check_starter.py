"""Inspect required official files and logger signatures; do not run grading or contact APIs."""
import ast
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
required=[
 'assignment2/evaluation_scripts/agent_task_input.json',
 'assignment2/evaluation_scripts/run_all.sh',
 'assignment2/evaluation_scripts/evaluate.sh',
 'assignment2/evaluation_scripts/make_patches.py',
 'assignment3/starter_code/src/sandbox.py',
 'assignment3/starter_code/src/sandbox_server.py',
 'assignment3/starter_code/dispatcher/dispatcher.py',
 'assignment3/starter_code/evaluation_scripts/trace_logger.py',
 'assignment3/starter_code/madsOpt.py']
missing=[p for p in required if not (ROOT/p).is_file()]
if missing:
    print('Official starter files missing:')
    print('\n'.join(missing))
    print('Run python scripts/install_official.py 2 and python scripts/install_official.py 3')
    sys.exit(1)
for rel in [required[4],required[6],required[7]]:
    print('\n'+rel)
    tree=ast.parse((ROOT/rel).read_text())
    for cls in (n for n in tree.body if isinstance(n,ast.ClassDef)):
        print('class',cls.name)
        for method in (n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))):
            if not method.name.startswith('_'):
                print(' ',method.name,ast.unparse(method.args))
print('\nCompare logger methods to src/adapters.py dispatcher_sink before a live run. File presence is not a compatibility test.')
