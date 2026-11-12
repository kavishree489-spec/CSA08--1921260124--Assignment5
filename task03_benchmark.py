"""B3: daily mean PM2.5 per station - loops vs pandas vs SQL (+ running-sum alternative)."""
import csv
import cProfile
import os
import pstats
import sqlite3
import statistics
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import generate_rows, write_csv  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def by_loops(path):
    """Store all readings, then statistics.mean()  -> O(n) time, O(n) space."""
    groups = defaultdict(list)
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            groups[(r["station"], r["date"])].append(float(r["pm25"]))
    return {k: statistics.mean(v) for k, v in groups.items()}


def by_running_sum(path):
    """One pass, running sum + count -> O(n) time, O(stations x days) space."""
    acc = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            k = (r["station"], r["date"])
            s, c = acc.get(k, (0.0, 0))
            acc[k] = (s + float(r["pm25"]), c + 1)
    return {k: s / c for k, (s, c) in acc.items()}


def by_pandas(path):
    df = pd.read_csv(path, usecols=["station", "date", "pm25"])
    return df.groupby(["station", "date"])["pm25"].mean().to_dict()


def by_sql(path, return_split=False):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE aq (station TEXT, day TEXT, pm25 REAL)")
    t0 = time.perf_counter()
    with open(path, newline="") as f:
        rd = csv.DictReader(f)
        con.executemany("INSERT INTO aq VALUES (?,?,?)", ((r["station"], r["date"], float(r["pm25"])) for r in rd))
    t1 = time.perf_counter()
    res = {(s, d): m for s, d, m in con.execute("SELECT station, day, AVG(pm25) FROM aq GROUP BY station, day")}
    t2 = time.perf_counter()
    con.close()
    return (res, t1 - t0, t2 - t1) if return_split else res


def agree(a, b):
    return a.keys() == b.keys() and all(abs(a[k] - b[k]) < 1e-6 for k in a)


def timed(fn, *args):
    t = time.perf_counter()
    r = fn(*args)
    return r, time.perf_counter() - t


if __name__ == "__main__":
    print("B3.1 Correctness on small data (2 stations x 7 days)")
    write_csv(generate_rows(2, days=7), "small.csv")
    r1, r2, r3, r4 = by_loops("small.csv"), by_pandas("small.csv"), by_sql("small.csv"), by_running_sum("small.csv")
    print("  loops == pandas      :", agree(r1, r2))
    print("  loops == SQL         :", agree(r1, r3))
    print("  loops == running-sum :", agree(r1, r4))
    assert agree(r1, r2) and agree(r1, r3) and agree(r1, r4)
    print("  sample:", list(r1.items())[:2])
    os.remove("small.csv")

    print("\nB3.2 Timing (seconds)")
    print(f"{'stations':>8} {'rows':>9} | {'loops':>7} {'run-sum':>8} {'pandas':>7} {'SQL total':>9} {'(load)':>7} {'(query)':>8}")
    mid_path = None
    for n in (1, 12, 120):
        rows = generate_rows(n, days=365)
        path = f"data_{n}.csv"
        write_csv(rows, path)
        _, t_loop = timed(by_loops, path)
        _, t_run = timed(by_running_sum, path)
        _, t_pd = timed(by_pandas, path)
        (_, t_load, t_q), t_sql = timed(by_sql, path, True)
        print(f"{n:>8} {len(rows):>9} | {t_loop:7.3f} {t_run:8.3f} {t_pd:7.3f} {t_sql:9.3f} {t_load:7.3f} {t_q:8.3f}")
        if n == 12:
            mid_path = path
        else:
            os.remove(path)

    print("\nB3.3 cProfile of the plain-Python loop version (12 stations)")
    pr = cProfile.Profile()
    pr.enable()
    by_loops(mid_path)
    pr.disable()
    pstats.Stats(pr).sort_stats("cumulative").print_stats(8)
    pstats.Stats(pr).sort_stats("tottime").print_stats(5)
    os.remove(mid_path)
