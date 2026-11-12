"""B1: cleaning pipeline -> SQLite (executemany) -> 3 SQL questions -> 4 charts."""
import csv
import os
import sqlite3
import statistics
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import generate_rows, write_csv  # noqa: E402

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FAHRENHEIT_STATIONS = {"guindy", "velachery"}          # stations that report degrees F
LIMITS = {"pm25": (0, 999), "pm10": (0, 1999), "no": (0, 999), "temp": (-10, 60)}  # temp in C
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")


# ---------- cleaning rules (see Part A2) ----------
def norm_station(name):
    return " ".join(name.split()).title()               # trim, single spaces, Title Case


def norm_date(text):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"bad date: {text!r}")


def to_float(text):
    text = (text or "").strip()
    if text == "" or text.upper() == "NA":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def clean_file(path):
    stats = {"rows_in": 0, "duplicates": 0, "impossible": 0, "missing": 0,
             "fahrenheit_converted": 0, "filled_prev": 0, "filled_median": 0}
    seen, rows = set(), []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            stats["rows_in"] += 1
            st, day, hour = norm_station(r["station"]), norm_date(r["date"]), int(r["hour"])
            key = (st, day, hour)
            if key in seen:                              # rule: duplicate rows -> keep first
                stats["duplicates"] += 1
                continue
            seen.add(key)
            rec = {"station": st, "date": day, "hour": hour}
            for col in ("pm25", "pm10", "no", "temp"):
                v = to_float(r[col])
                if v is None:
                    stats["missing"] += 1
                else:
                    if col == "temp" and st.lower() in FAHRENHEIT_STATIONS:
                        v = round((v - 32) * 5 / 9, 1)   # rule: F -> C
                        stats["fahrenheit_converted"] += 1
                    lo, hi = LIMITS[col]
                    if not lo <= v <= hi:                # rule: impossible -> missing
                        stats["impossible"] += 1
                        v = None
                rec[col] = v
            rows.append(rec)

    rows.sort(key=lambda x: (x["station"], x["date"], x["hour"]))
    # rule: missing -> previous valid value of the same station (forward fill)
    last = {}
    for rec in rows:
        for col in ("pm25", "pm10", "no", "temp"):
            if rec[col] is None:
                prev = last.get((rec["station"], col))
                if prev is not None:
                    rec[col] = prev
                    stats["filled_prev"] += 1
            else:
                last[(rec["station"], col)] = rec[col]
    # leading gaps (no previous value) -> station median
    med = {}
    for rec in rows:
        for col in ("pm25", "pm10", "no", "temp"):
            if rec[col] is None:
                k = (rec["station"], col)
                if k not in med:
                    vals = [x[col] for x in rows if x["station"] == rec["station"] and x[col] is not None]
                    med[k] = statistics.median(vals) if vals else None
                rec[col] = med[k]
                stats["filled_median"] += 1
    return rows, stats


def min_max(values):
    lo, hi = min(values), max(values)
    return [0.0] * len(values) if hi == lo else [(v - lo) / (hi - lo) for v in values]


def z_score(values):
    m, s = statistics.mean(values), statistics.pstdev(values)
    return [0.0] * len(values) if s == 0 else [(v - m) / s for v in values]


# ---------- B1.1 validation on a small file with every problem ----------
SMALL = """station,date,hour,pm25,pm10,no,temp
Adyar,2026-10-01,0,48,80,20,28.0
Adyar,2026-10-01,1,NA,82,21,28.5
Adyar,2026-10-01,2,,85,22,29.0
Adyar,2026-10-01,3,-5,84,22,29.2
Adyar,2026-10-01,4,5000,86,23,29.4
Adyar,2026-10-01,4,5000,86,23,29.4
  adyar ,02/10/2026,0,52,90,24,29.0
guindy,2026-10-01,0,95,150,40,86.0
GUINDY,2026-10-01,1,,155,41,87.8
"""


def validate_small():
    path = os.path.join(HERE, "small_messy.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write(SMALL)
    print("=== BEFORE CLEANING ===")
    print(SMALL)
    rows, stats = clean_file(path)
    print("=== AFTER CLEANING ===")
    for r in rows:
        print(r)
    print("\nStatistics:", stats)
    assert len(rows) == 8 and all(r["pm25"] is not None for r in rows)
    assert all(0 <= r["pm25"] <= 999 for r in rows)
    assert [r for r in rows if r["station"] == "Guindy"][0]["temp"] == 30.0   # 86 F = 30 C
    print("All assertions passed.\n")


# ---------- B1.3 SQLite ----------
SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
    station_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS readings (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL REFERENCES stations(station_id),
    day        TEXT NOT NULL,           -- YYYY-MM-DD
    hour       INTEGER NOT NULL CHECK (hour BETWEEN 0 AND 23),
    pm25 REAL, pm10 REAL, no REAL, temp_c REAL,
    UNIQUE (station_id, day, hour)
);
"""


def store(rows, db_path):
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.executemany("INSERT OR IGNORE INTO stations(name) VALUES (?)",
                    [(n,) for n in sorted({r["station"] for r in rows})])
    ids = dict(con.execute("SELECT name, station_id FROM stations"))
    con.executemany(
        "INSERT INTO readings(station_id, day, hour, pm25, pm10, no, temp_c) VALUES (?,?,?,?,?,?,?)",
        [(ids[r["station"]], r["date"], r["hour"], r["pm25"], r["pm10"], r["no"], r["temp"]) for r in rows])
    con.commit()
    return con


def questions(con):
    print("Q1. Average PM2.5 of Adyar in October 2026")
    print("   ", con.execute("""SELECT ROUND(AVG(pm25),2) FROM readings r JOIN stations s USING(station_id)
                                WHERE s.name = ? AND r.day BETWEEN ? AND ?""",
                              ("Adyar", "2026-10-01", "2026-10-31")).fetchone()[0])
    print("Q2. Stations ranked by mean PM2.5")
    for row in con.execute("""SELECT s.name, ROUND(AVG(pm25),2) a FROM readings r JOIN stations s USING(station_id)
                              GROUP BY s.name ORDER BY a DESC LIMIT 3"""):
        print("   ", row)
    print("Q3. Three worst hours of the day (all stations)")
    for row in con.execute("""SELECT hour, ROUND(AVG(pm25),2) a FROM readings GROUP BY hour
                              ORDER BY a DESC LIMIT 3"""):
        print("   ", row)


# ---------- B1.4 charts ----------
def charts(con):
    out = os.path.join(HERE, "charts")
    os.makedirs(out, exist_ok=True)

    d = con.execute("""SELECT day, AVG(pm25) FROM readings r JOIN stations s USING(station_id)
                       WHERE s.name='Adyar' GROUP BY day ORDER BY day""").fetchall()
    plt.figure(figsize=(9, 4))
    plt.plot([x[0][8:] for x in d], [x[1] for x in d], marker="o")
    plt.title("Adyar - daily mean PM2.5, October 2026")
    plt.xlabel("Day of month"); plt.ylabel("PM2.5 (µg/m³)"); plt.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(f"{out}/1_trend_line.png", dpi=120); plt.close()

    s = con.execute("""SELECT s.name, AVG(pm25) FROM readings r JOIN stations s USING(station_id)
                       GROUP BY s.name ORDER BY 2 DESC""").fetchall()
    plt.figure(figsize=(7, 4))
    plt.bar([x[0] for x in s], [x[1] for x in s], color="tab:orange")
    plt.title("Mean PM2.5 by station"); plt.xlabel("Station"); plt.ylabel("PM2.5 (µg/m³)")
    plt.tight_layout(); plt.savefig(f"{out}/2_station_bar.png", dpi=120); plt.close()

    t = con.execute("SELECT temp_c, pm25 FROM readings").fetchall()
    plt.figure(figsize=(6, 5))
    plt.scatter([x[0] for x in t], [x[1] for x in t], s=6, alpha=.4)
    plt.title("Temperature vs PM2.5"); plt.xlabel("Temperature (°C)"); plt.ylabel("PM2.5 (µg/m³)")
    plt.tight_layout(); plt.savefig(f"{out}/3_temp_vs_pm25_scatter.png", dpi=120); plt.close()

    groups = [[x[0] for x in con.execute("SELECT pm25 FROM readings WHERE hour=?", (h,))] for h in range(24)]
    plt.figure(figsize=(10, 4))
    plt.boxplot(groups, tick_labels=range(24), showfliers=False)
    plt.title("PM2.5 by hour of day"); plt.xlabel("Hour"); plt.ylabel("PM2.5 (µg/m³)")
    plt.tight_layout(); plt.savefig(f"{out}/4_hour_boxplot.png", dpi=120); plt.close()
    print("Charts saved in", out)


if __name__ == "__main__":
    validate_small()

    raw_rows = generate_rows(4, start=date(2026, 10, 1), days=31, faults=True,
                             fahrenheit={"Guindy", "Velachery"})
    raw = os.path.join(HERE, "october_raw.csv")
    write_csv(raw_rows, raw)
    rows, stats = clean_file(raw)
    print("October file cleaned:", stats)

    pm = [r["pm25"] for r in rows]
    print("min-max sample:", [round(x, 3) for x in min_max(pm)[:5]])
    print("z-score sample:", [round(x, 3) for x in z_score(pm)[:5]])

    con = store(rows, os.path.join(HERE, "airquality.db"))
    questions(con)
    charts(con)
    con.close()
