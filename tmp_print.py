import json
from pathlib import Path
text = Path("betterSB/dataMerger(testing).ipynb").read_text()
idx = text.index("dataset_entries")
print(text[idx-400:idx+400])
