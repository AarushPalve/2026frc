import json
from pathlib import Path
path = Path('betterSB/dataMerger(testing).ipynb')
data = json.loads(path.read_text())
changed = False
target = "        score_diff = alliance_data.get('score_difference')\n        error_value = alliance_data.get('difference')\n"
replacement = "        score_diff = alliance_data.get('difference')\n        error_value = alliance_data.get('error_value')\n"
for cell in data['cells']:
    if cell.get('cell_type') != 'code':
        continue
    source = ''.join(cell.get('source', []))
    if target in source:
        updated = source.replace(target, replacement, 1)
        cell['source'] = [line + ('\n' if line and not line.endswith('\n') else '') for line in updated.split('\n')]
        changed = True
        break
if not changed:
    raise SystemExit('pattern not found')
path.write_text(json.dumps(data, indent=1))
