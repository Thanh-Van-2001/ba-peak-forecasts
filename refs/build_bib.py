"""Build refs.bib from Crossref BibTeX for DOIs (fails loudly if a DOI does not resolve)
and print each title for a by-eye check. Manual entries live in refs/manual.bib.
Run: python build_bib.py <out.bib>"""
import os
import re
import sys
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "ref-check/0.1 (academic reference verification)"}
DOIS = {
    "lerch2017dilemma": "10.1214/16-STS588",
    "gneiting2011point": "10.1198/jasa.2011.r10138",
    "murphy1993good": "10.1175/1520-0434(1993)008<0281:wiagfa>2.0.co;2",
    "hong2016probabilistic": "10.1016/j.ijforecast.2015.11.011",
    "auffhammer2017climate": "10.1073/pnas.1613193114",
    "xie2018temperature": "10.1109/TSG.2016.2597178",
    "sobhani2020temperature": "10.1016/j.ijforecast.2019.04.022",
    "ruggles2020eia": "10.1038/s41597-020-0483-x",
    "menne2012ghcn": "10.1175/JTECH-D-11-00103.1",
    "dersimonian1986meta": "10.1016/0197-2456(86)90046-2",
    "kunsch1989jackknife": "10.1214/aos/1176347265",
    "newey1987simple": "10.2307/1913610",
}
TITLE_FIX = {}


def get(url, tries=5):
    for t in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code != 429 or t == tries - 1:
                raise
            time.sleep(20 * (t + 1))


out = []
for key, doi in DOIS.items():
    bib = get(f"https://api.crossref.org/works/{doi}/transform/application/x-bibtex")
    bib = re.sub(r"^@(\w+)\{[^,]+,", lambda m: "@" + m.group(1) + "{" + key + ",", bib.strip(), count=1)
    bib = re.sub(r"\s*url=\{[^}]*\},", "", bib)
    bib = re.sub(r",\s*month=\w+", "", bib)
    for a, b in TITLE_FIX.items():
        bib = bib.replace(a, b)
    t = re.search(r"title=\{(.*?)\},", bib)
    print(f"{key:26s} {t.group(1)[:95] if t else '??'}")
    out.append(bib)
    time.sleep(0.5)
manual = open(os.path.join(os.path.dirname(__file__), "manual.bib"), encoding="utf-8").read()
open(sys.argv[1], "w", encoding="utf-8").write("\n\n".join(out) + "\n\n" + manual)
print(len(out) + manual.count("\n@") + manual.startswith("@"), "entries written")
