# Do grid operators under-forecast peak load?

Code, analysis plan and results for the paper "Do Grid Operators Under-Forecast Peak Load? Selection, Heat and a Decade of Day-Ahead Forecasts in U.S. Balancing Authorities" (submitted to IEEE PowerTech 2027).

- `PLAN.md`: the analysis plan, committed before any forecast error was computed, with Amendment 1 (bug fixes and exploratory analyses added after the results).
- `code/download_eia930.sh`: downloads the EIA-930 six-month BALANCE files and writes SHA-256 hashes.
- `code/extract_all.py`: extracts every balancing authority into one parquet file.
- `code/download_weather.py`: downloads NOAA GHCN-Daily maximum temperature for the cities listed in `PLAN.md` and picks one station per city (`out/station_choice.json`, hashes in `out/weather_SHA256SUMS`).
- `code/peaks.py`: the analysis (`--check` runs the pipeline check). Writes `out/results.json` and `out/ba_table.csv`.
- `code/make_macros.py`, `code/make_figures.py`: every number and figure in `paper/`.

Run order: download, extract, weather, `peaks.py`, macros, figures, then `pdflatex`/`bibtex` in `paper/`.
Python 3.11 with pandas 2.2.3, numpy 1.26.4, scipy 1.14.1, statsmodels 0.14.4, pyarrow 17.0.0, matplotlib 3.9.2.
