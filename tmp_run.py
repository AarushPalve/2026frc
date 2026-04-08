import json
from pathlib import Path

ipynb_path = Path('betterSB/dataMerger.ipynb')
data = json.loads(ipynb_path.read_text())
code = ''.join(data['cells'][1]['source'])
exec_globals = {'__name__': '__main__'}
exec(compile(code, str(ipynb_path), 'exec'), exec_globals)
