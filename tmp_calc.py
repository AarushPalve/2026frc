import json
import pandas as pd
from pathlib import Path
pick_df = pd.read_csv('2026orwil - Picklist.csv')
pick_df.columns = pick_df.columns.str.strip()
rename_map = {'BPS 1': 'bps_auto', 'BPS 2': 'bps_tele', 'avg_BPS': 'bps_avg', 'accuracy 1': 'acc_auto', 'acc 2': 'acc_tele', 'avg acc': 'acc_avg'}
pick_df = pick_df.rename(columns=rename_map)
def safe_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
picklist = {}
for row in pick_df.itertuples(index=False):
    team_key = getattr(row, 'key', None)
    if not isinstance(team_key, str) or not team_key.startswith('frc'):
        continue
    picklist[team_key] = {
        'auto_bps': safe_number(getattr(row, 'bps_auto', None)) or safe_number(getattr(row, 'bps_avg', None)),
        'tele_bps': safe_number(getattr(row, 'bps_tele', None)) or safe_number(getattr(row, 'bps_avg', None)),
        'auto_acc': safe_number(getattr(row, 'acc_auto', None)) or safe_number(getattr(row, 'acc_avg', None)),
        'tele_acc': safe_number(getattr(row, 'acc_tele', None)) or safe_number(getattr(row, 'acc_avg', None)),
    }
match = json.load(open('betterSB/orwilmatchmath(1).json'))['matches'][0]
for team_record in match['teams']:
    if team_record['team_key'] == 'frc3673':
        info = picklist.get(team_record['team_key'])
        def compute(points, bps, acc):
            p = safe_number(points)
            b = safe_number(bps)
            a = safe_number(acc)
            if p is None or b is None or a is None:
                return None
            denom = b * a
            if denom == 0:
                return None
            return p / denom
        print('info', info)
        print('auto_time', compute(team_record.get('selected_auto'), info['auto_bps'], info['auto_acc']))
        print('tele_time', compute(team_record.get('selected_teleop'), info['tele_bps'], info['tele_acc']))
        break
