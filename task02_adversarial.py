"""B2: adversarial files, SQL injection, and sentiment-scorer failures."""
import csv
import io
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
REQUIRED = {"station", "date", "pm25"}
GOOD = "station,date,pm25\nAdyar,2026-10-01,48\nGuindy,2026-10-01,95\n"


def make_files():
    d = os.path.join(HERE, "adversarial_inputs")
    os.makedirs(d, exist_ok=True)
    files = {
        "missing_column.csv": ("station,date\nAdyar,2026-10-01\n", "utf-8"),
        "wrong_delimiter.csv": (GOOD.replace(",", ";"), "utf-8"),
        "latin1.csv": ("station,date,pm25\nCafé Road,2026-10-01,48\n", "latin-1"),
        "utf16.csv": (GOOD, "utf-16"),
        "empty.csv": ("", "utf-8"),
    }
    paths = {}
    for name, (text, enc) in files.items():
        p = os.path.join(d, name)
        with open(p, "w", encoding=enc, newline="") as f:
            f.write(text)
        paths[name] = p
    return paths


def naive_load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [(r["station"], r["date"], float(r["pm25"])) for r in csv.DictReader(f)]


def safe_load(path):
    """Robust loader: detects empty file, encoding, delimiter and missing columns."""
    with open(path, "rb") as f:
        raw = f.read()
    if not raw.strip():
        raise ValueError("file is empty")
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):           # UTF-16 byte-order mark
        used = "utf-16"
    else:
        try:
            raw.decode("utf-8-sig")
            used = "utf-8-sig"
        except UnicodeDecodeError:
            used = "latin-1"                           # never fails, so it is the last resort
    text = raw.decode(used)
    first = text.splitlines()[0]
    delim = max(",;\t|", key=first.count)
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    missing = REQUIRED - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"missing column(s): {sorted(missing)}")
    rows = [(r["station"], r["date"], float(r["pm25"])) for r in reader]
    return rows, used, delim


def file_tests():
    print("=" * 70, "\nPART 1 - adversarial files\n" + "=" * 70)
    for name, path in make_files().items():
        print(f"\n[{name}]")
        try:
            print("  naive :", naive_load(path))
        except Exception as e:
            print(f"  naive : {type(e).__name__}: {e}")
        try:
            print("  robust:", safe_load(path))
        except Exception as e:
            print(f"  robust: rejected cleanly -> {e}")


def injection_tests():
    print("\n" + "=" * 70, "\nPART 2 - SQL injection / quote in station name\n" + "=" * 70)
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE aq (station TEXT, day TEXT, pm25 REAL)")
    con.executemany("INSERT INTO aq VALUES (?,?,?)",
                    [("Adyar", "d1", 48.0), ("Guindy", "d1", 95.0), ("O'Brien Road", "d1", 70.0)])
    evil = "Adyar' OR '1'='1"

    print("\n1) String concatenation with +")
    sql = "SELECT AVG(pm25) FROM aq WHERE station = '" + evil + "'"
    print("   SQL sent:", sql)
    print("   result  :", con.execute(sql).fetchone()[0], "<- average of ALL rows: injection worked")

    try:
        con.execute("SELECT AVG(pm25) FROM aq WHERE station = '" + "O'Brien Road" + "'")
    except sqlite3.Error as e:
        print("   legitimate name O'Brien Road breaks the query:", e)

    try:
        con.execute("SELECT 1 WHERE 1=0; DROP TABLE aq; --")
    except Exception as e:
        print("   stacked statement refused by execute():", type(e).__name__)
    print("   (executescript() would run stacked statements - never use it with user input)")

    print("\n2) Parameterised query with ?")
    q = "SELECT AVG(pm25) FROM aq WHERE station = ?"
    print("   evil input      ->", con.execute(q, (evil,)).fetchone()[0], "(treated as plain text, no match)")
    print("   O'Brien Road    ->", con.execute(q, ("O'Brien Road",)).fetchone()[0], "(quote handled correctly)")
    con.close()


POS = {"good", "clean", "fast", "helpful", "improved", "great", "love", "excellent"}
NEG = {"bad", "dirty", "slow", "rude", "smoke", "broken", "terrible", "worst"}
NEGATORS = {"not", "never", "no"}


def score(text):
    words = text.lower().replace(".", " ").replace(",", " ").replace("!", " ").split()
    total = 0
    for i, w in enumerate(words):
        v = 1 if w in POS else -1 if w in NEG else 0
        if v and i > 0 and words[i - 1] in NEGATORS:
            v = -v
        total += v
    return total


def sentiment_tests():
    print("\n" + "=" * 70, "\nPART 3 - sentiment scorer stress test\n" + "=" * 70)
    cases = [
        ("Oh great, another broken streetlight. Just what I needed.", "negative", "sarcasm"),
        ("Yeah, the clean air is so fast I cannot even see it.", "negative", "sarcasm"),
        ("It is not that the service is not good.", "positive", "double negative"),
        ("I can't say the road is not bad.", "negative", "double negative / contraction"),
        ("The staff were helpful but the office was dirty and slow.", "mixed", "mixed opinions"),
        ("Good roads, terrible smoke.", "mixed", "mixed opinions"),
        ("The staff were not helpful.", "negative", "control (should pass)"),
    ]
    fails = 0
    for text, truth, kind in cases:
        s = score(text)
        got = "positive" if s > 0 else "negative" if s < 0 else "neutral"
        ok = got == truth or (truth == "mixed" and got == "neutral")
        fails += not ok
        print(f"[{'ok  ' if ok else 'FAIL'}] {kind:30} score={s:+d} got={got:8} truth={truth:8} | {text}")
    print(f"\n{fails} of {len(cases)} cases failed.")


if __name__ == "__main__":
    file_tests()
    injection_tests()
    sentiment_tests()
