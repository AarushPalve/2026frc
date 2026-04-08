from pathlib import Path
text = Path("betterSB/dataMerger(testing).ipynb").read_text()
print(text.count("score_diff = alliance_data.get('difference')"))
print(text.count("error_value = alliance_data.get('error_value')"))
