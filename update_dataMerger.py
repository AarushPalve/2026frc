import json, pathlib
path = pathlib.Path('betterSB/dataMerger.ipynb')
data = json.loads(path.read_text())
code = '.join(data['cells'][1]['source'])
start = code.index('def best_alignment(')
