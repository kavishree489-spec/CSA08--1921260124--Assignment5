import csv
import io

RAW = """station,date,pm25
Adyar,2026-10-01,48
Adyar,2026-10-02,NA
Adyar,2026-10-03,
Guindy,2026-10-01,95
Guindy,2026-10-02,-5
Guindy,2026-10-03,121
Guindy,2026-10-04,5000
"""  # last row is the extra test row for the "> 999" check

MAX_PM25 = 999


def load_clean(text):
    """Returns (station, date, pm25) tuples for valid, non-negative readings only."""
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        raw = (r["pm25"] or "").strip()
        if raw == "" or raw.upper() == "NA":
            continue
        value = float(raw)
        if value < 0 or value > MAX_PM25:      # negative or impossible (sensor fault)
            continue
        rows.append((r["station"], r["date"], value))
    return rows


def min_max(values):
    lo, hi = min(values), max(values)
    if hi == lo:                                # avoid division by zero
        return [0.0 for _ in values]
    return [round((v - lo) / (hi - lo), 3) for v in values]


clean = load_clean(RAW)
print(clean)
print(min_max([pm for _, _, pm in clean]))
