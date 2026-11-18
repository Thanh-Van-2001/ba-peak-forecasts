"""Download NOAA GHCN-Daily TMAX for the cities in PLAN.md and pick one station per city.

Rule (PLAN.md, Weather): nearest station whose ID begins with USW, within 100 km,
with TMAX on >= 95% of days in 2016-01-01..2026-09-30; if none, the nearest
station of any type that qualifies. Candidates come from the GHCN inventory
(TMAX first year <= 2016 and last year >= 2026). Files are written atomically
(.part then os.replace) and hashed in data/weather/SHA256SUMS.
Run: python -I download_weather.py <repo_root>
"""
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.request

ROOT = sys.argv[1]
W = os.path.join(ROOT, "data", "weather")
os.makedirs(os.path.join(W, "raw"), exist_ok=True)
BASE = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/"
API = ("https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations={}"
       "&startDate=2016-01-01&endDate=2026-09-30&dataTypes=TMAX&format=csv&units=metric")
NDAYS = 3926  # 2016-01-01..2026-09-30 inclusive


def fetch(url, path, tries=4):
    if os.path.exists(path):
        return path
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=300) as r, open(path + ".part", "wb") as f:
                f.write(r.read())
            os.replace(path + ".part", path)
            return path
        except Exception as e:  # network errors are retried, then raised
            print("retry", k, url, e, flush=True)
            time.sleep(10 * (k + 1))
    raise RuntimeError(url)


def km(a, b, c, d):
    p = math.pi / 180
    h = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


cities = {}
for line in open(os.path.join(ROOT, "PLAN.md"), encoding="utf-8"):
    m = re.match(r"\| ([A-Z]{2,5}) \| (.+) \|$", line.strip())
    if m:
        for name, lat, lon in re.findall(r"([^;(]+?) \((-?[\d.]+), (-?[\d.]+)\)", m.group(2)):
            cities.setdefault(name.strip(), (float(lat), float(lon)))
print(len(cities), "cities", flush=True)

st = fetch(BASE + "ghcnd-stations.txt", os.path.join(W, "ghcnd-stations.txt"))
inv = fetch(BASE + "ghcnd-inventory.txt", os.path.join(W, "ghcnd-inventory.txt"))
ok = set()
for line in open(inv):
    sid, el, y0, y1 = line[0:11], line[31:35], int(line[36:40]), int(line[41:45])
    if el == "TMAX" and y0 <= 2016 and y1 >= 2026 and sid.startswith("US"):
        ok.add(sid)
stations = {}
for line in open(st):
    sid = line[0:11]
    if sid in ok:
        stations[sid] = (float(line[12:20]), float(line[21:30]), line[41:71].strip())

choice = {}
for name, (la, lo) in sorted(cities.items()):
    cand = sorted((km(la, lo, s[0], s[1]), sid) for sid, s in stations.items())
    cand = [c for c in cand if c[0] <= 100]
    picked = None
    for tier in (True, False):
        for dist, sid in cand:
            if sid.startswith("USW") != tier and tier:
                continue
            f = fetch(API.format(sid), os.path.join(W, "raw", sid + ".csv"))
            n = sum(1 for row in open(f) if '"TMAX"' not in row and row.strip() and row.split(",")[-1].strip('"\n '))
            if n >= 0.95 * NDAYS:
                picked = {"station": sid, "name": stations[sid][2], "km": round(dist, 1), "days": n, "usw": sid.startswith("USW")}
                break
        if picked:
            break
    choice[name] = picked
    print(name, picked, flush=True)

json.dump(choice, open(os.path.join(W, "station_choice.json"), "w"), indent=1)
with open(os.path.join(W, "SHA256SUMS"), "w") as h:
    for f in sorted(os.listdir(os.path.join(W, "raw"))):
        h.write(hashlib.sha256(open(os.path.join(W, "raw", f), "rb").read()).hexdigest() + "  raw/" + f + "\n")
print("done", sum(v is not None for v in choice.values()), "of", len(choice))
