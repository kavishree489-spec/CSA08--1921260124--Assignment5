"""B4: sentiment scorer + extractive summariser on 50 complaints, agreement check,
first-k alternative, index timing, and the production-scale estimate."""
import os
import re
import sqlite3
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import generate_rows  # noqa: E402

POS = {"good", "clean", "fast", "helpful", "improved", "great", "better", "quick", "polite",
       "excellent", "resolved", "thanks", "prompt", "cleaner", "responsive"}
NEG = {"bad", "dirty", "slow", "rude", "smoke", "broken", "terrible", "worst", "noise", "stink",
       "ignored", "delay", "delayed", "pollution", "polluted", "choking", "unsafe", "dust", "ignoring"}
NEGATORS = {"not", "never", "no", "hardly"}
STOP = set("the a an is are was were and or but of to in on at for with from it this that i my we our "
           "has have had be been very so as by they them their there still again just".split())

# (complaint, my own label)
COMPLAINTS = [
    ("The air near the factory is terrible. Smoke every morning. Nobody listens.", "negative"),
    ("Garbage burning on our street again. The smoke is choking children. Please act.", "negative"),
    ("Thanks to the team, the air monitor was fixed quickly. Very helpful staff.", "positive"),
    ("Bus service has improved a lot. Buses are clean and fast now.", "positive"),
    ("The helpline staff were not helpful. They were rude and ignored my call.", "negative"),
    ("Road dust is unbearable. Construction trucks never cover their loads. Dust everywhere.", "negative"),
    ("Complaint resolved within a day. Polite officer, excellent response.", "positive"),
    ("The new sensor display is good. I can read the PM2.5 value easily.", "positive"),
    ("Noise from the highway is bad at night. The pollution is also bad.", "negative"),
    ("Not bad, the park is cleaner than last year.", "positive"),
    ("Drain is broken and it stinks. Mosquitoes everywhere. Nobody responded.", "negative"),
    ("Please share the monthly report. I want to read the station data.", "neutral"),
    ("What time does the Adyar station update its readings?", "neutral"),
    ("The app is slow and keeps crashing. Dirty air and a bad app.", "negative"),
    ("Streetlights are working now. Thank you for the quick repair, great work.", "positive"),
    ("Smoke from the brick kiln is terrible. The officials delayed action for months.", "negative"),
    ("The water supply was fast to restore. Staff were polite and prompt.", "positive"),
    ("I am requesting a meeting about the Guindy readings next week.", "neutral"),
    ("Burning of leaves continues. Delay in action is unacceptable. Air is bad.", "negative"),
    ("The sensor near my school is broken. It shows no data since Monday.", "negative"),
    ("Cleaner air this month. The new rules are better and helpful.", "positive"),
    ("The officer was not rude. He was polite and explained everything.", "positive"),
    ("Truck traffic is the worst at 8 pm. Smoke and noise together.", "negative"),
    ("Please send details of the complaint number 2231.", "neutral"),
    ("The footpath is dirty and broken. Not safe for the elderly.", "negative"),
    ("Good initiative to put sensors in schools. Children will be safe.", "positive"),
    ("Service was slow but the staff were helpful in the end.", "neutral"),
    ("Great, another day of smoke. Wonderful job, officials.", "negative"),   # sarcasm
    ("Wow, so helpful. I waited three hours for a reply.", "negative"),       # sarcasm
    ("The factory pollution is bad but the road is clean.", "neutral"),        # mixed
    ("Not good. The report is late and the numbers look wrong.", "negative"),
    ("Pollution never improved in my area. Still choking.", "negative"),
    ("The bus was quick and clean. Driver was polite.", "positive"),
    ("I would like to know the permitted PM10 limit.", "neutral"),
    ("Dust from the metro work is terrible. Please sprinkle water.", "negative"),
    ("Complaint ignored for two weeks. Rude reply from the office.", "negative"),
    ("The air quality board website is excellent. Data is clear.", "positive"),
    ("The market is dirty and smells. Garbage not cleared for days.", "negative"),
    ("Thanks for the update. Readings are better after the rain.", "positive"),
    ("Is the Velachery station working today?", "neutral"),
    ("Smoke from the crematorium is bad. Choking at night.", "negative"),
    ("Not happy. Nobody came to inspect. No reply to emails.", "negative"),
    ("The new bus stop is clean and the shade is good.", "positive"),
    ("Your team never ignored my request. Resolved quickly, thanks.", "positive"),
    ("Please add a station near Ambattur. The nearest one is far away.", "neutral"),
    ("Pollution is unsafe for kids. Smoke, dust and noise all day.", "negative"),
    ("Response was fast and the staff were helpful. Excellent.", "positive"),
    ("The pothole repair is slow. Road is broken and dirty.", "negative"),
    ("Better air today. Not a single smoke complaint on my street.", "positive"),
    ("I read the report. Nothing else to add.", "neutral"),
]


def words_of(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def score(text):
    w = words_of(text)
    total = 0
    for i, x in enumerate(w):
        v = 1 if x in POS else -1 if x in NEG else 0
        if v and i > 0 and w[i - 1] in NEGATORS:
            v = -v
        total += v
    return total


def label(text):
    s = score(text)
    return "positive" if s > 0 else "negative" if s < 0 else "neutral"


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def build_freq(texts):
    return Counter(w for t in texts for w in words_of(t) if w not in STOP and len(w) > 2)


def summarise(text, freq, k=1):
    """Extractive: keep the k sentences with the highest total frequency of important words."""
    sents = sentences(text)
    ranked = sorted(range(len(sents)), key=lambda i: -sum(freq[w] for w in words_of(sents[i]) if w not in STOP))
    keep = sorted(ranked[:k])
    return " ".join(sents[i] for i in keep)


def first_k(text, k=1):
    return " ".join(sentences(text)[:k])


def part_b41():
    texts = [c for c, _ in COMPLAINTS]
    mine = [l for _, l in COMPLAINTS]
    predicted = [label(t) for t in texts]
    agree = sum(p == m for p, m in zip(predicted, mine))
    print(f"B4.1 Sentiment agreement with my labels: {agree}/{len(texts)} = {agree / len(texts):.0%}")
    for t, p, m in zip(texts, predicted, mine):
        if p != m:
            print(f"   MISMATCH scorer={p:8} me={m:8} | {t}")

    freq = build_freq(texts)
    print("\nTop important words:", freq.most_common(8))
    keep_ext = keep_first = 0
    for t in texts:
        full = label(t)
        keep_ext += label(summarise(t, freq)) == full
        keep_first += label(first_k(t)) == full
    print(f"\nSummary keeps the sentiment of the full complaint (k=1 sentence):")
    print(f"   frequency-based summariser : {keep_ext}/{len(texts)}")
    print(f"   first-sentence summariser  : {keep_first}/{len(texts)}")
    print("\nExample:")
    ex = COMPLAINTS[0][0]
    print("   full   :", ex)
    print("   summary:", summarise(ex, freq))

    t = time.perf_counter()
    for _ in range(2000):
        for x in texts:
            label(x)
    per = (time.perf_counter() - t) / (2000 * len(texts))
    t = time.perf_counter()
    for _ in range(200):
        for x in texts:
            summarise(x, freq)
    per_s = (time.perf_counter() - t) / (200 * len(texts))
    t = time.perf_counter()
    for _ in range(2000):
        for x in texts:
            first_k(x)
    per_f = (time.perf_counter() - t) / (2000 * len(texts))
    print(f"\nTime per complaint: scorer {per * 1e6:.1f} us | freq-summary {per_s * 1e6:.1f} us | first-k {per_f * 1e6:.1f} us")
    print(f"50,000 complaints/month -> scorer ~{per * 50000:.2f} s, summary ~{per_s * 50000:.2f} s")


def part_b42():
    print("\nB4.2 Index on (station, day) - 120 stations x 8,760 rows (~1.05M rows)")
    rows = generate_rows(120, days=365)
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE aq (station TEXT, day TEXT, hour INT, pm25 REAL)")
    con.executemany("INSERT INTO aq VALUES (?,?,?,?)", ((r[0], r[1], r[2], r[3]) for r in rows))
    con.commit()
    q = "SELECT AVG(pm25) FROM aq WHERE station = ? AND day = ?"
    args = ("Station100", "2026-06-15")

    def run(n):
        t = time.perf_counter()
        for _ in range(n):
            con.execute(q, args).fetchone()
        return (time.perf_counter() - t) / n

    print("  plan before:", con.execute("EXPLAIN QUERY PLAN " + q, args).fetchall()[0][-1])
    before = run(20)
    t = time.perf_counter()
    con.execute("CREATE INDEX idx_station_day ON aq(station, day)")
    build = time.perf_counter() - t
    print("  plan after :", con.execute("EXPLAIN QUERY PLAN " + q, args).fetchall()[0][-1])
    after = run(2000)
    print(f"  per query: before {before * 1000:.3f} ms | after {after * 1000:.4f} ms | speed-up x{before / after:,.0f}")
    print(f"  index build time {build:.2f} s (one-off cost)")
    con.close()
    return before, after


if __name__ == "__main__":
    part_b41()
    part_b42()
    print("\nB4.3 Scale estimate: 112 stations x 96 readings/day x 365 = "
          f"{112 * 96 * 365:,} rows/year per measurement (~{112 * 96 * 365 / 1e6:.1f} M rows).")
