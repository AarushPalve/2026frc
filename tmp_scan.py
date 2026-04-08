import json
from pathlib import Path
path = Path('betterSB/dataMerger(testing).ipynb')
data = json.loads(path.read_text())
for cell in data['cells']:
    if cell.get('cell_type') != 'code':
        continue
    src = cell.get('source', [])
    for i,line in enumerate(src):
        if 'score_diff' in line:
            print(i, repr(line))
            print(repr(src[i-1]))
            print(repr(src[i+1]))
            raise SystemExit
