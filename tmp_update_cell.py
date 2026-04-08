import json
from pathlib import Path
import sqlite3
import math

import pandas as pd
import shutil

BASE_DIR = Path('C:/Users/Aarush/Documents/FRC/2026Scripts')
MATCH_JSON = BASE_DIR / 'betterSB' / 'Caismatchmath.json'
PICKLIST_CSV = BASE_DIR / 'caisTeam.csv'
MATCH_DB = BASE_DIR / 'match.db'

CLONE_DB = MATCH_DB.with_name('2' + MATCH_DB.name)
shutil.copy2(MATCH_DB, CLONE_DB)
print('Cloned database to', CLONE_DB)

print('JSON path:', MATCH_JSON)
print('Picklist:', PICKLIST_CSV)
print('Database:', MATCH_DB)


def safe_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(num):
        return None
    return num


def compute_time(points, bps, accuracy):
    points = safe_number(points)
    bps = safe_number(bps)
    accuracy = safe_number(accuracy)
    if points is None or bps is None or accuracy is None:
        return None
    denom = bps * accuracy
    if denom == 0 or math.isnan(denom):
        return None
    return points / denom


PHASE_SCORING_KEYS = {
    'auto': 'auto_points',
    'teleop': 'tele_points',
}


def get_selected_points(team_record, phase):
    selected_key = f'selected_{phase}'
    selected_value = team_record.get(selected_key)
    if selected_value is not None:
        return selected_value
    scouting_points = team_record.get('points', {}).get('scouting', {})
    fallback_key = PHASE_SCORING_KEYS.get(phase)
    if fallback_key:
        return scouting_points.get(fallback_key)
    return None


with MATCH_JSON.open() as match_file:
    match_data = json.load(match_file)
matches = match_data.get('matches') or []
print(f'Loaded {len(matches)} matches from {MATCH_JSON.name}')

picklist = {}
picklist_df = pd.read_csv(PICKLIST_CSV)
for record in picklist_df.to_dict('records'):
    team_key = record.get('team_key') or record.get('key')
    if not isinstance(team_key, str):
        continue
    team_key = team_key.strip().lower()
    if not team_key:
        continue
    metrics = {
        'auto_bps': safe_number(record.get('bps_1')),
        'tele_bps': None,
        'auto_acc': safe_number(record.get('accuracy_1')),
        'tele_acc': None,
    }
    if metrics['auto_bps'] is None and metrics['auto_acc'] is None:
        continue
    picklist[team_key] = metrics

print(
    f'Loaded scoring-rate metrics for {len(picklist)} teams',
    f'from {PICKLIST_CSV.name}'
)
