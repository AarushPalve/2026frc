from collections import Counter, defaultdict
from pathlib import Path
import json
from datetime import datetime, timezone
from itertools import product
from statistics import mean
import math
import pandas as pd

epa_data_path = Path('orwil_epa_data.json')
opr_data_path = Path('2026orwil_opr_data.json')
scouting_data_path = Path('2026orwil_scouting_data(1).json')
match_data_path = Path('2026orwil_matches.json')
output_path = Path('orwilmatchmath(2).json')
print(output_path)

SCOUTING_POINT_MAP = {
    'auto_points': 'a_points',
    'tele_points': 'tele_fuel',
    'total_points': 'total_points',
    'tower_points': 'tower_points',
}
EPA_POINT_MAP = {
    'auto_points': 'auto_points',
    'tele_points': 'teleop_points',
    'total_points': 'total_points',
    'tower_points': 'total_tower',
}
OPR_POINT_MAP = {
    'auto_points': 'totalAutoPoints',
    'tele_points': 'totalTeleopPoints',
    'total_points': 'totalPoints',
    'tower_points': 'totalTowerPoints',
}

STAGE_KEYS = [
    ('auto', 'auto_points'),
    ('teleop', 'tele_points'),
    ('tower', 'tower_points'),
]

try:
    import statbotics
    sb = statbotics.Statbotics()
    score_sd_response = sb.get_year(2026, fields=['score_sd'])
except Exception:
    score_sd_response = {'score_sd': None}

raw_score_sd = score_sd_response.get('score_sd')
try:
    SCORE_SD_VALUE = float(raw_score_sd) if raw_score_sd is not None else 1.0
except (TypeError, ValueError):
    SCORE_SD_VALUE = 1.0
if not SCORE_SD_VALUE:
    SCORE_SD_VALUE = 1.0

K = -5/8
print(f"Using score SD value: {SCORE_SD_VALUE}")
try:
    import statbotics
    sb = statbotics.Statbotics()
    score_sd_response = sb.get_year(2026, fields=['score_sd'])
except Exception:
    score_sd_response = {'score_sd': None}

raw_score_sd = score_sd_response.get('score_sd')
try:
    SCORE_SD_VALUE = float(raw_score_sd) if raw_score_sd is not None else 1.0
except (TypeError, ValueError):
    SCORE_SD_VALUE = 1.0
if not SCORE_SD_VALUE:
    SCORE_SD_VALUE = 1.0

K = -5/8

def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f'{path} is missing.')
    return json.loads(path.read_text())

def parse_team_key(team_key):
    if isinstance(team_key, str) and team_key.lower().startswith('frc'):
        return int(team_key[3:])
    return int(team_key)



def calc_win_odds(k, score_sd_value, red_score, blue_score):
    if not score_sd_value:
        return 0.5
    norm_diff = (red_score - blue_score) / score_sd_value
    exponent = (k * norm_diff) * math.log(10)
    exponent = max(-700, min(700, exponent))
    exp_term = math.exp(exponent)
    return 1 / (1 + exp_term)

def team_future_average(prior_selected, team_id, candidate_value):
    values = prior_selected.get(team_id, [])[-3:]
    combined = list(values)
    if candidate_value is not None:
        combined.append(candidate_value)
    if not combined:
        return 0.0
    return sum(combined) / len(combined)


def win_odds_penalty(alliance, match_scores, candidate_avg, red_team_ids, blue_team_ids, prior_selected, score_sd_value, k):
    winning_alliance = match_scores.get('winning_alliance')
    if winning_alliance is None or score_sd_value <= 0:
        return 0.0
    red_pred = candidate_avg if alliance == 'red' else sum(team_future_average(prior_selected, team_id, None) for team_id in red_team_ids)
    blue_pred = candidate_avg if alliance == 'blue' else sum(team_future_average(prior_selected, team_id, None) for team_id in blue_team_ids)
    red_odds = calc_win_odds(k, score_sd_value, red_pred, blue_pred)
    win_odds_for_alliance = red_odds if alliance == 'red' else 1 - red_odds
    actual_outcome = 1.0 if winning_alliance == alliance else 0.0
    return abs(win_odds_for_alliance - actual_outcome) * score_sd_value

def best_alignment(team_rows, target_score, alliance, match_scores, red_team_ids, blue_team_ids, prior_selected, score_sd_value, k, score_weight=1.0, penalty_weight=1.0):
    option_lists = []
    for row in team_rows:
        options = available_metrics_for_row(row)
        if not options:
            return None
        option_lists.append(options)
    if not option_lists or target_score is None:
        return None
    team_ids = [row['team'] for row in team_rows]
    best_combo = None
    best_error = float('inf')
    best_total = None
    best_diff = None
    best_penalty = 0.0
    for combo in product(*option_lists):
        total = sum(option['value'] for option in combo)
        diff = abs(total - target_score)
        candidate_avg = sum(team_future_average(prior_selected, team_id, option['value']) for team_id, option in zip(team_ids, combo))
        penalty = win_odds_penalty(alliance, match_scores, candidate_avg, red_team_ids, blue_team_ids, prior_selected, score_sd_value, k)
        cost = score_weight * diff + penalty_weight * penalty
        if cost < best_error:
            best_error = cost
            best_total = total
            best_diff = diff
            best_penalty = penalty
            best_combo = combo
    if best_combo is None:
        return None
    metrics_used = []
    for row, option in zip(team_rows, best_combo):
        stage_values = option.get('stage_values', {})
        stage_total = stage_values.get('total')
        row['selected_metric'] = option.get('metric')
        row['selected_value'] = option.get('value')
        row['selected_total'] = stage_total if stage_total is not None else option.get('value')
        row['selected_auto'] = stage_values.get('auto')
        row['selected_teleop'] = stage_values.get('teleop')
        row['selected_tower'] = stage_values.get('tower')
        metrics_used.extend(option.get('metrics', []))
    return {
        'total': round(best_total, 3),
        'difference': round(best_diff, 3),
        'error_value': round(best_error, 3),
        'win_penalty': round(best_penalty, 3),
        'metrics': metrics_used,
    }


def map_points(metrics, mapping):
    if not metrics:
        return None
    mapped = {dest: metrics.get(src) for dest, src in mapping.items()}
    if any(value is not None for value in mapped.values()):
        return mapped
    return None

def compute_total_from_points(points):
    if not points:
        return None
    total = points.get('total_points')
    if total is not None:
        return total
    components = [points.get('auto_points'), points.get('tele_points'), points.get('tower_points')]
    if any(value is not None for value in components):
        return sum(value or 0.0 for value in components if value is not None)
    return None

def available_metrics_for_row(row):
    options = []
    points = row.get('points', {})
    match_number = row.get('match_number') or 0
    allow_opr_metrics = match_number > 42

    def stage_breakdown(metric_key):
        breakdown = points.get(metric_key) or {}
        return {
            'auto': safe_score(breakdown.get('auto_points')),
            'teleop': safe_score(breakdown.get('tele_points')),
            'tower': safe_score(breakdown.get('tower_points')),
        }

    def add_aggregated(metric_label, total_value):
        if total_value is None:
            return
        breakdown = stage_breakdown(metric_label)
        options.append({
            'metric': metric_label,
            'value': total_value,
            'metrics': [metric_label],
            'stage_values': {
                'auto': breakdown['auto'],
                'teleop': breakdown['teleop'],
                'tower': breakdown['tower'],
                'total': total_value,
            },
        })

    scouting_total = compute_total_from_points(points.get('scouting'))
    add_aggregated('scouting', scouting_total)

    epa_value = row.get('epa')
    if epa_value is None:
        epa_value = compute_total_from_points(points.get('epa'))
    add_aggregated('epa', epa_value)

    opr_value = row.get('opr')
    if allow_opr_metrics:
        add_aggregated('opr', opr_value)

    stage_candidates = []
    stage_metric_labels = ('scouting', 'epa', 'opr') if allow_opr_metrics else ('scouting', 'epa')
    for stage_name, stage_key in STAGE_KEYS:
        stage_options = []
        for metric_label in stage_metric_labels:
            breakdown = points.get(metric_label) or {}
            value = safe_score(breakdown.get(stage_key))
            if value is not None:
                stage_options.append({
                    'stage': stage_name,
                    'metric': metric_label,
                    'value': value,
                })
        if not stage_options:
            stage_candidates = []
            break
        stage_candidates.append(stage_options)

    if stage_candidates:
        for combo in product(*stage_candidates):
            stage_values = {choice['stage']: choice['value'] for choice in combo}
            total = sum(choice['value'] for choice in combo)
            options.append({
                'metric': 'stage_combo',
                'value': total,
                'metrics': sorted({choice['metric'] for choice in combo}),
                'stage_values': {
                    'auto': stage_values.get('auto'),
                    'teleop': stage_values.get('teleop'),
                    'tower': stage_values.get('tower'),
                    'total': total,
                },
            })

    return options


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def safe_score(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

epa_data = load_json(epa_data_path)
opr_data = load_json(opr_data_path)
scouting_data = load_json(scouting_data_path)
matches = load_json(match_data_path)

qual_matches = [match for match in matches if match.get('comp_level') == 'qm']

def match_sort_key(match):
    return (safe_int(match.get('set_number'), 0), safe_int(match.get('match_number'), 0))

qual_matches_sorted = sorted(qual_matches, key=match_sort_key)
team_played_counts = Counter()
match_order_info = []
for match in qual_matches_sorted:
    team_ids = []
    for alliance in ('red', 'blue'):
        team_keys = match.get('alliances', {}).get(alliance, {}).get('team_keys', []) or []
        for team_key in team_keys:
            team_ids.append(parse_team_key(team_key))
    allowed_opr = {team_id: team_played_counts[team_id] >= 8 for team_id in team_ids}
    match_order_info.append({
        'match': match,
        'team_ids': team_ids,
        'allowed_opr': allowed_opr,
    })
    for team_id in team_ids:
        team_played_counts[team_id] += 1

match_team_stats = {}
for record in scouting_data.get('matches', []):
    match_key = record['match_key']
    bucket = match_team_stats.setdefault(match_key, {})
    for team in record.get('teams', []):
        team_id = int(team['team'])
        team_stats = bucket.setdefault(team_id, {})
        points = map_points(team.get('metrics'), SCOUTING_POINT_MAP)
        if points:
            team_stats.setdefault('points', {})['scouting'] = points

for record in epa_data.get('matches', []):
    match_key = record['match_key']
    bucket = match_team_stats.setdefault(match_key, {})
    for team in record.get('teams', []):
        team_id = int(team['team'])
        team_stats = bucket.setdefault(team_id, {})
        epa_obj = team.get('epa', {})
        epa_value = epa_obj.get('post_match_total') or epa_obj.get('pre_match_total')
        if epa_value is not None:
            team_stats['epa'] = epa_value
        points = map_points(epa_obj.get('breakdown', {}), EPA_POINT_MAP)
        if points:
            team_stats.setdefault('points', {})['epa'] = points

for record in opr_data.get('matches', []):
    match_key = record['match_key']
    bucket = match_team_stats.setdefault(match_key, {})
    for team in record.get('teams', []):
        team_id = int(team['team'])
        team_stats = bucket.setdefault(team_id, {})
        opr_value = team.get('opr')
        if opr_value is not None:
            team_stats['opr'] = opr_value
        points = map_points(team.get('copr'), OPR_POINT_MAP)
        if points:
            team_stats.setdefault('points', {})['opr'] = points


PASS_CONFIGS = [
    {'score_weight': 1.0, 'penalty_weight': 0.25},
    {'score_weight': 0.8, 'penalty_weight': 1.0},
    {'score_weight': 0.5, 'penalty_weight': 2.0},
    {'score_weight': 0.3, 'penalty_weight': 4.0},
]


def append_history(prior_selected, team_id, value):
    if value is None:
        return
    history = prior_selected.setdefault(team_id, [])
    history.append(value)
    if len(history) > 3:
        prior_selected[team_id] = history[-3:]


def run_alignment_pass(score_weight, penalty_weight, base_history=None, collect_output=False):
    prior_selected = defaultdict(list)
    if base_history:
        for team_id, values in base_history.items():
            prior_selected[team_id] = values[-3:].copy()
    matches_output = [] if collect_output else None
    metric_usage = Counter()
    debug_rows = []
    for info in match_order_info:
        match = info['match']
        match_key = match.get('key')
        if not match_key:
            continue
        stats_for_match = match_team_stats.get(match_key, {})
        allowed_opr = info['allowed_opr']
        alliances = match.get('alliances', {})
        match_scores = {
            'red': alliances.get('red', {}).get('score'),
            'blue': alliances.get('blue', {}).get('score'),
            'winning_alliance': match.get('winning_alliance'),
        }
        alliance_team_ids = {
            color: [parse_team_key(team_key) for team_key in alliances.get(color, {}).get('team_keys', []) or []]
            for color in ('red', 'blue')
        }
        alliances_data = {} if collect_output else None
        team_rows = [] if collect_output else None
        for alliance in ('red', 'blue'):
            alliance_info = alliances.get(alliance, {})
            score = alliance_info.get('score')
            team_keys = alliance_info.get('team_keys', []) or []
            alliance_rows = []
            for team_key in team_keys:
                team_id = parse_team_key(team_key)
                stats = stats_for_match.get(team_id, {})
                alliance_rows.append({
                    'team_key': team_key,
                    'team': team_id,
                    'alliance': alliance,
                    'epa': stats.get('epa'),
                    'opr': stats.get('opr') if allowed_opr.get(team_id) else None,
                    'points': stats.get('points', {}),
                    'match_number': safe_int(match.get('match_number')),
                })
            best = best_alignment(
                alliance_rows,
                score,
                alliance,
                match_scores,
                alliance_team_ids['red'],
                alliance_team_ids['blue'],
                prior_selected,
                SCORE_SD_VALUE,
                K,
                score_weight=score_weight,
                penalty_weight=penalty_weight,
            )
            if best is not None:
                for row in alliance_rows:
                    history_value = row.get('selected_total')
                    if history_value is None:
                        history_value = row.get('selected_value')
                    append_history(prior_selected, row['team'], history_value)
                if collect_output:
                    metric_usage.update(best['metrics'])
            if collect_output and best is None:
                for row in alliance_rows:
                    row['selected_metric'] = None
                    row['selected_value'] = None
                    row['selected_total'] = None
                    row['selected_auto'] = None
                    row['selected_teleop'] = None
                    row['selected_tower'] = None
            if collect_output:
                alliances_data[alliance] = {
                    'score': score,
                    'selected_total': best['total'] if best else None,
                    'difference': best['difference'] if best else None,
                    'error_value': best['error_value'] if best else None,
                    'win_penalty': best['win_penalty'] if best else None,
                    'selected_metrics': best['metrics'] if best else None,
                }
                team_rows.extend(alliance_rows)
        if collect_output:
            matches_output.append({
                'match_key': match_key,
                'event_key': match.get('event_key'),
                'comp_level': match.get('comp_level'),
                'set_number': match.get('set_number'),
                'match_number': match.get('match_number'),
                'time': match.get('time'),
                'status': 'completed' if match.get('post_result_time') else 'scheduled',
                'winning_alliance': match.get('winning_alliance'),
                'alliances': alliances_data,
                'teams': team_rows,
            })
            diffs = [abs(alliance.get('difference')) for alliance in alliances_data.values() if alliance.get('difference') is not None]
            errors = [alliance.get('error_value') for alliance in alliances_data.values() if alliance.get('error_value') is not None]
            match_diff = mean(diffs) if diffs else None
            match_error = mean(errors) if errors else None
            red_total = alliances_data['red']['selected_total']
            blue_total = alliances_data['blue']['selected_total']
            red_pred_value = red_total if red_total is not None else 0.0
            blue_pred_value = blue_total if blue_total is not None else 0.0
            red_win_odds = calc_win_odds(K, SCORE_SD_VALUE, red_pred_value, blue_pred_value)
            blue_win_odds = 1 - red_win_odds
            debug_entry = {
                'match_key': match_key,
                'match_number': safe_int(match.get('match_number')),
                'difference': match_diff,
                'error_value': match_error,
                'red_difference': alliances_data['red'].get('difference'),
                'blue_difference': alliances_data['blue'].get('difference'),
                'score_sd': SCORE_SD_VALUE,
                'merged_red_total': red_total,
                'merged_blue_total': blue_total,
                'red_win_odds': red_win_odds,
                'blue_win_odds': blue_win_odds,
                'score_sd_red': SCORE_SD_VALUE * red_win_odds,
                'score_sd_blue': SCORE_SD_VALUE * blue_win_odds,
            }
            debug_rows.append(debug_entry)
    history_snapshot = {team: values.copy() for team, values in prior_selected.items()}
    return {
        'matches_output': matches_output,
        'history': history_snapshot,
        'metric_usage': metric_usage,
        'debug_rows': debug_rows,
    }

history = None
final_result = None
for idx, params in enumerate(PASS_CONFIGS):
    collect_output = idx == len(PASS_CONFIGS) - 1
    result = run_alignment_pass(
        params['score_weight'],
        params['penalty_weight'],
        history,
        collect_output,
    )
    history = result['history']
    if collect_output:
        final_result = result

if final_result is None:
    raise RuntimeError('No alignment pass produced output.')

matches_output = final_result['matches_output']
metric_usage = final_result['metric_usage']
debug_rows = final_result['debug_rows']
merged_diff_rows = []
for match in matches_output:
    diffs = [abs(alliance.get('difference')) for alliance in match['alliances'].values() if alliance.get('difference') is not None]
    errors = [alliance.get('error_value') for alliance in match['alliances'].values() if alliance.get('error_value') is not None]
    match_diff = mean(diffs) if diffs else None
    match_error = mean(errors) if errors else None
    if match_diff is not None or match_error is not None:
        merged_diff_rows.append({
            'match_key': match['match_key'],
            'match_number': safe_int(match.get('match_number')),
            'comp_level': match.get('comp_level'),
            'difference': match_diff,
            'error_value': match_error,
        })

output_data = {
    'event': epa_data.get('event') or (qual_matches_sorted[0].get('event_key') if qual_matches_sorted else 'unknown-event'),
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'sources': {
        'epa': epa_data_path.name,
        'opr': opr_data_path.name,
        'scouting': scouting_data_path.name,
        'matches': match_data_path.name,
    },
    'matches': matches_output,
}
output_path.write_text(json.dumps(output_data, indent=2))

differences = [row['difference'] for row in merged_diff_rows if row.get('difference') is not None]
error_values = [row['error_value'] for row in merged_diff_rows if row.get('error_value') is not None]
print(f'Wrote {len(matches_output)} matches to {output_path.name}')
if differences:
    print(f'mean gap {sum(differences)/len(differences):.2f}, max gap {max(differences):.2f}')
else:
    print('No alliances had enough data to compare yet.')
if error_values:
    print(f'mean error function {sum(error_values)/len(error_values):.2f}, max error function {max(error_values):.2f}')
else:
    print('No error values available yet.')

if debug_rows:
    pd.DataFrame(debug_rows).to_csv(Path('dataMergerDebug.csv'), index=False)
    print(f'Saved debug data to dataMergerDebug.csv')

actual_matches = {info['match'].get('key'): info['match'] for info in match_order_info if info['match'].get('key')}

def collect_diffs(predictions):
    getter = getattr(predictions, 'get', None)
    if getter is None or not callable(getter):
        getter = predictions
    rows = []
    for match_key, actual in actual_matches.items():
        predicted = getter(match_key)
        if not predicted:
            continue
        alliance_diffs = []
        for alliance, actual_info in actual['alliances'].items():
            score = safe_score(actual_info.get('score'))
            if score is None:
                continue
            pred_value = predicted.get(alliance)
            if pred_value is None:
                continue
            alliance_diffs.append(abs(pred_value - score))
        if not alliance_diffs:
            continue
        rows.append({
            'match_key': match_key,
            'match_number': int(actual['match_number']),
            'comp_level': actual.get('comp_level'),
            'difference': mean(alliance_diffs),
        })
    return rows

scouting_by_match = {
    record['match_key']: record
    for record in scouting_data.get('matches', [])
    if record.get('match_key')
}

scouting_predictions = {}
for match_key, match in actual_matches.items():
    scouting_match = scouting_by_match.get(match_key)
    if not scouting_match:
        continue
    totals = {'red': 0.0, 'blue': 0.0}
    seen = {'red': False, 'blue': False}
    for team in scouting_match.get('teams', []):
        alliance = team.get('alliance')
        points = map_points(team.get('metrics'), SCOUTING_POINT_MAP)
        total_amount = compute_total_from_points(points)
        if total_amount is not None:
            totals[alliance] += total_amount
            seen[alliance] = True
    aggregated = {alliance: (totals[alliance] if seen[alliance] else None) for alliance in totals}
    if any(seen.values()):
        scouting_predictions[match_key] = aggregated

epa_predictions = {}
for record in epa_data.get('matches', []):
    match_key = record.get('match_key')
    if match_key not in actual_matches:
        continue
    totals = {'red': 0.0, 'blue': 0.0}
    seen = {'red': False, 'blue': False}
    for team in record.get('teams', []):
        alliance = team.get('alliance')
        epa_total = team.get('epa', {}).get('pre_match_total') or team.get('epa', {}).get('post_match_total')
        if epa_total is not None:
            totals[alliance] += epa_total
            seen[alliance] = True
    aggregated = {alliance: (totals[alliance] if seen[alliance] else None) for alliance in totals}
    if any(seen.values()):
        epa_predictions[match_key] = aggregated

opr_predictions = {}
opr_matches = {
    record['match_key']: record
    for record in opr_data.get('matches', [])
    if record.get('match_key')
}
for info in match_order_info:
    match_key = info['match'].get('key')
    if not match_key or match_key not in actual_matches:
        continue
    allowed = info['allowed_opr']
    if not allowed or not all(allowed.values()):
        continue
    opr_match = opr_matches.get(match_key)
    if not opr_match:
        continue
    totals = {'red': 0.0, 'blue': 0.0}
    seen = {'red': False, 'blue': False}
    for team in opr_match.get('teams', []):
        alliance = team.get('alliance')
        opr_value = team.get('opr')
        if opr_value is not None:
            totals[alliance] += opr_value
            seen[alliance] = True
    aggregated = {alliance: (totals[alliance] if seen[alliance] else None) for alliance in totals}
    if any(seen.values()):
        opr_predictions[match_key] = aggregated

prediction_sources = [
    ('scouting', scouting_predictions),
    ('tba', epa_predictions),
    ('statbotics', opr_predictions),
]
for row in debug_rows:
    match_key = row['match_key']
    for label, source in prediction_sources:
        totals = source.get(match_key, {})
        row[f'{label}_red_total'] = totals.get('red')
        row[f'{label}_blue_total'] = totals.get('blue')

difference_records = []



def describe_dataset(label, entries):
    if not entries:
        print(f"{label}: no data")
        return
    sorted_entries = sorted(entries, key=lambda row: (safe_int(row.get('match_number')), row.get('match_key')))
    values = [row['difference'] for row in sorted_entries]
    print(f"{label}: mean gap {mean(values):.2f}, max gap {max(values):.2f}")
    error_values = [row.get('error_value') for row in sorted_entries if row.get('error_value') is not None]
    if error_values:
        print(f"{label}: mean error function {mean(error_values):.2f}, max error function {max(error_values):.2f}")
    for record in sorted_entries:
        actual = actual_matches.get(record['match_key'], {})
        difference_records.append({
            **record,
            'source': label,
            'match_json': json.dumps(actual),
            'alliances_json': json.dumps(actual.get('alliances', {})),
            'teams_json': json.dumps(actual.get('teams', [])),
            'error_value': record.get('error_value'),
        })
        print(f"  {label} {record['match_key']} (match {record['match_number']}): diff {record['difference']:.2f}")
dataset_entries = [
    ('Scouting totals', collect_diffs(scouting_predictions)),
    ('TBA (Orwil pre-match EPA)', collect_diffs(epa_predictions)),
    ('Statbotics (OPR)', collect_diffs(opr_predictions)),
    ('Merged selection', merged_diff_rows),
]

for label, entries in dataset_entries:
    describe_dataset(label, entries)

print('Metric usage counts:')
for metric, count in metric_usage.most_common():
    print(f"  {metric}: {count}")

export_matches_csv = True
matches_csv_path = Path('match_data.csv')
if export_matches_csv:
    rows = []
    for match in matches_output:
        row = {
            'event': output_data['event'],
            'generated_at': output_data['generated_at'],
            'source_epa': output_data['sources']['epa'],
            'source_opr': output_data['sources']['opr'],
            'source_scouting': output_data['sources']['scouting'],
            'source_matches': output_data['sources']['matches'],
            'match_key': match.get('match_key'),
            'event_key': match.get('event_key'),
            'set_number': match.get('set_number'),
            'match_number': match.get('match_number'),
            'time': match.get('time'),
            'status': match.get('status'),
            'winning_alliance': match.get('winning_alliance'),
            'alliances': json.dumps(match.get('alliances', {})),
            'teams': json.dumps(match.get('teams', [])),
        }
        rows.append({**row, 'match_json': json.dumps(match)})
    pd.DataFrame(rows).to_csv(matches_csv_path, index=False)
    print(f"Saved match data to {matches_csv_path}")

if difference_records:
    pd.DataFrame(difference_records).to_csv(Path('difference_data.csv'), index=False)
    print("Saved difference data to difference_data.csv")




