"""Shared helpers: synthetic air-quality data generator and CSV writer."""
import csv
import math
import random
from datetime import date, timedelta

STATIONS = ["Adyar", "Guindy", "Velachery", "T Nagar", "Anna Nagar", "Mylapore",
            "Perungudi", "Tondiarpet", "Royapuram", "Ambattur", "Alandur", "Manali"]
HEADER = ["station", "date", "hour", "pm25", "pm10", "no", "temp"]


def station_name(i):
    return STATIONS[i] if i < len(STATIONS) else f"Station{i + 1}"


def generate_rows(n_stations, start=date(2026, 1, 1), days=365, seed=42,
                  faults=False, fahrenheit=()):
    """Hourly readings: n_stations * days * 24 rows (8,760 per station for a year).
    faults=True injects blanks, 'NA', negatives and impossible values.
    Stations listed in `fahrenheit` report temperature in degrees F."""
    rnd = random.Random(seed)
    rows = []
    for s in range(n_stations):
        name = station_name(s)
        base = rnd.uniform(40, 90)
        for d in range(days):
            ds = (start + timedelta(days=d)).isoformat()
            for h in range(24):
                temp_c = 27 + 5 * math.sin((h - 9) / 24 * 2 * math.pi) + rnd.gauss(0, 1)
                peak = math.exp(-((h - 8) ** 2) / 8) + math.exp(-((h - 20) ** 2) / 8)
                pm25 = max(1.0, base + 35 * peak - 1.0 * (temp_c - 27) + rnd.gauss(0, 8))
                pm10 = pm25 * 1.6 + rnd.gauss(0, 5)
                no = max(1.0, 0.4 * pm25 + rnd.gauss(0, 4))
                temp = temp_c * 9 / 5 + 32 if name in fahrenheit else temp_c
                pm25, pm10, no, temp = round(pm25, 1), round(pm10, 1), round(no, 1), round(temp, 1)
                if faults:
                    r = rnd.random()
                    if r < 0.02:
                        pm25 = ""
                    elif r < 0.03:
                        pm25 = "NA"
                    elif r < 0.04:
                        pm25 = -5
                    elif r < 0.045:
                        pm25 = 5000
                rows.append((name, ds, h, pm25, pm10, no, temp))
    return rows


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
