import json
from pathlib import Path
matches = json.loads(Path('betterSB/2026orwil_matches.json').read_text())
print(matches[0].keys())
print(matches[0]['key'])
print(matches[0].get('match_key'))
print(matches[0]['alliances'].keys())
