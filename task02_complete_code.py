import sqlite3

readings = [("Adyar", "2026-10-01", 48.0), ("Guindy", "2026-10-01", 95.0),
            ("Guindy", "2026-10-03", 121.0), ("Adyar", "2026-10-04", 60.0)]

con = sqlite3.connect(":memory:")
con.execute("CREATE TABLE aq (station TEXT, day TEXT, pm25 REAL)")

con.executemany("INSERT INTO aq (station, day, pm25) VALUES (?, ?, ?)", readings)
con.commit()


def station_average(name):
    row = con.execute("SELECT AVG(pm25) FROM aq WHERE station = ?", (name,)).fetchone()
    return row[0]          # AVG of zero rows is NULL -> None


print(station_average("Adyar"), station_average("Guindy"))
print(station_average("Adyar' OR '1'='1"))   # an injection attempt finds nothing
con.close()

# WHY None? The ? placeholder sends the whole text "Adyar' OR '1'='1" as ONE data value.
# SQLite compares station to that literal string; no station has that name, so no rows
# match and AVG() returns NULL (None). The quote is never parsed as SQL syntax.
