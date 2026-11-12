"""B1 alternative: cleaning with pandas vs csv loops at 1k, 100k, 1M rows (time + peak memory)."""
import csv
import os
import sys
import time
import tracemalloc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import generate_rows, write_csv  # noqa: E402
import pandas as pd  # noqa: E402


def loops_clean(path):
    out = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            raw = r["pm25"].strip()
            if raw == "" or raw.upper() == "NA":
                continue
            v = float(raw)
            if 0 <= v <= 999:
                out.append(v)
    lo, hi = min(out), max(out)
    return [(v - lo) / (hi - lo) for v in out]


def pandas_clean(path):
    df = pd.read_csv(path, usecols=["pm25"], na_values=["NA", ""])
    s = df["pm25"]
    s = s[(s >= 0) & (s <= 999)].dropna()
    return (s - s.min()) / (s.max() - s.min())


def measure(fn, path):
    tracemalloc.start()
    t = time.perf_counter()
    res = fn(path)
    dt = time.perf_counter() - t
    peak = tracemalloc.get_traced_memory()[1] / 1e6
    tracemalloc.stop()
    return dt, peak, len(res)


if __name__ == "__main__":
    print(f"{'rows':>10} | {'method':8} | {'time (s)':>9} | {'peak MB':>8} | kept")
    for n_rows in (1_000, 100_000, 1_000_000):
        stations = max(1, round(n_rows / 8760))
        rows = generate_rows(stations, days=365, faults=True)[:n_rows]
        path = f"_tmp_{n_rows}.csv"
        write_csv(rows, path)
        for name, fn in (("loops", loops_clean), ("pandas", pandas_clean)):
            dt, peak, kept = measure(fn, path)
            print(f"{n_rows:>10} | {name:8} | {dt:9.4f} | {peak:8.1f} | {kept}")
        os.remove(path)
