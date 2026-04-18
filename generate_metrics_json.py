#!/usr/bin/env python3
"""Build per-team OPR-like metrics JSON using match scoring times and picklist BPS."""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
MATCH_CSV = BASE_DIR / "pncmpMatch.csv"
PICKLIST_CSV = BASE_DIR / "pncmpTeam.csv"
OUTPUT_FILE = BASE_DIR / "betterSB" / "2026pncmp_scouting_data.json"
METRIC_NAMES = ["a_points", "a_fuel", "tele_fuel", "tower_points", "total_points"]
print(MATCH_CSV)
print(PICKLIST_CSV)
CSV_FIELD_LIMIT = 1 << 24
try:
    csv.field_size_limit(CSV_FIELD_LIMIT)
except OverflowError:
    csv.field_size_limit(sys.maxsize)


def to_float(value: Any) -> float:
    if value in (None, "", "None"):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def team_number(team_key: str) -> Optional[int]:
    if not team_key:
        return None
    team_key = team_key.strip()
    if team_key.lower().startswith("frc"):
        team_key = team_key[3:]
    try:
        return int(team_key)
    except ValueError:
        return None


def load_picklist() -> Dict[int, Dict[str, float]]:
    teams: Dict[int, Dict[str, float]] = {}
    if not PICKLIST_CSV.exists():
        return teams
    with PICKLIST_CSV.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            team = team_number(row.get("key", ""))
            if team is None:
                continue
            avg_bps = to_float(
                row.get("bps_1") or row.get("bps 1") or row.get("avg_BPS")
            )
            accuracy = to_float(
                row.get("accuracy 1")
                or row.get("accuracy_1")
                or row.get("avg_acc")
            )
            teams[team] = {
                "avg_bps": avg_bps,
                "accuracy": accuracy if accuracy is not None else 1.0,
            }
    return teams


def build_matches(picklist: Dict[int, Dict[str, float]]) -> List[Dict[str, Any]]:
    if not MATCH_CSV.exists():
        raise SystemExit(f"missing match CSV: {MATCH_CSV}")
    matches: Dict[str, Dict[str, Any]] = {}
    with MATCH_CSV.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            norm = {
                key.strip().lower(): value
                for key, value in row.items()
                if isinstance(key, str)
            }
            scout_init = norm.get("scout_init") or norm.get("scoutername")
            if not scout_init or not str(scout_init).strip():
                continue
            match_key = norm.get("key")
            if not match_key:
                continue
            if match_key not in matches:
                matches[match_key] = {
                    "match_key": match_key,
                    "time": None,
                    "status": norm.get("comp_level"),
                    "teams": [],
                }
            team = team_number(row.get("team_key", ""))
            if team is None:
                continue
            stats = picklist.get(team, {})
            bps = stats.get("avg_bps", 0.0)
            accuracy = stats.get("accuracy", 1.0) or 1.0
            a_time = to_float(norm.get("a_scoringtime"))
            t_time = to_float(norm.get("t_scoringtime"))
            a_climb = to_float(norm.get("a_climb"))
            end_climb = to_float(norm.get("end_climb"))
            a_points = a_time * bps * accuracy + a_climb
            tele_points = t_time * bps * accuracy
            tower_points = a_climb + end_climb
            metrics = {
                "a_points": a_points,
                "a_fuel": a_time * bps,
                "tele_fuel": tele_points,
                "tower_points": tower_points,
                "total_points": a_points + tele_points + tower_points,
            }
            matches[match_key]["teams"].append(
                {
                    "team": team,
                    "alliance": norm.get("alliance", row.get("alliance")),
                    "metrics": metrics,
                    "avg_bps": bps,
                    "a_scoring_time": a_time,
                    "t_scoring_time": t_time,
                    "a_climb": a_climb,
                    "end_climb": end_climb,
                }
            )
    return list(matches.values())


def main() -> None:
    picklist = load_picklist()
    matches = build_matches(picklist)
    payload = {
        "event": "2026orwil",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "components": METRIC_NAMES,
        "matches": matches,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
