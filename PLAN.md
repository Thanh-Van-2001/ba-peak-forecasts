# Analysis plan: do US balancing authorities under-forecast peak load?

Status: fixed before any forecast error was computed. Changes after this commit
are logged as amendments at the end, with the reason and what they change.

Target venue: IEEE PowerTech 2027 (full paper, IEEE format).

## What was looked at before this plan

- The EIA-930 six-month BALANCE files (July 2015 to the November 2026 vintage),
  already downloaded for an earlier study (cp-forecast-value), with SHA-256 sums.
- Data availability only: for each balancing authority (BA) and year, the share
  of hours with a reported demand and a reported day-ahead demand forecast, and
  each BA's median demand. No forecast error was computed for this study.
- The author's earlier study used the same files for four BAs (ERCOT, PJM,
  NYISO, ISO-NE) and computed forecast errors there, so errors for those four BAs
  have been seen in another context (mean absolute error, coincident-peak capture),
  but not the peak-day bias statistics defined below.
- Non-peer-reviewed public scorecards report that operator forecasts are low at
  the daily peak hour in most hours (for example 59% of days). Those statistics
  condition on the actual peak. This study asks how much of that is selection.

## Question

Operator day-ahead forecasts look low on peak days. Is this a genuine bias of
the forecasts, or a selection effect of evaluating them on days chosen by the
outcome? Does the error grow in heat, and has it changed over 2016 to 2026?

The selection argument: if a forecast is calibrated, E[D | F] = F, then days
picked because the actual load D was high are days on which D exceeded F more
often than not, so the forecast looks low even though it is not biased. Picking
days by the forecast F does not have this problem. A genuine under-forecast of
peaks therefore shows up as a negative bias on days with a high forecast.

## Data

- Source: Form EIA-930 hourly Demand (MW) and Demand Forecast (MW) as reported
  by each BA. EIA describes the forecast as the BA's day-ahead forecast.
- Window: local days 2016-01-01 to 2026-09-30 (EIA "Data Date").
- Weather: NOAA GHCN-Daily maximum temperature (TMAX), downloaded after this plan
  from the NCEI access-data service, for the cities in the table below.

### Sample (rule applied in code)

Primary sample: BAs whose median hourly demand over the window is at least
500 MW and whose demand and forecast are both present in at least 80% of hours
in at least 8 of the 11 calendar years 2016 to 2026 (2026 counted to the end
of the file). From the availability table this is expected to give about
43 BAs; the code decides.

Secondary sample: all BAs meeting the coverage rule without the size floor.

### Screening (same rule as the cp-forecast-value study, amendment 4)

For each BA, the centred 168-hour rolling median of positive reported demand
(min 24 values) is the reference. A demand or forecast value is set to missing
if it is <= 0, above 2.0 x the reference or below 0.3 x the reference. A local
day enters the day-level analysis only if every hour of that day has both a
screened demand and a screened forecast.

## Day-level quantities (per BA and local day d)

- D*_d: maximum hourly demand of the day; F*_d: maximum hourly forecast.
- Peak-magnitude error p_d = 100 x (F*_d - D*_d) / D*_d (percent; negative =
  forecast too low).
- Peak-hour error e_d = 100 x (F_h - D_h) / D_h at the hour h of D*_d
  (secondary).
- Daily MAPE (descriptive).

## Conditioning sets (within each BA and calendar year, to remove load growth)

- A-top: days whose D*_d is in the top 5% of that BA-year.
- F-top: days whose F*_d is in the top 5% of that BA-year.
- Ties at the cut-off are kept (all days >= the 95th percentile value).

## Weather

For each BA, the cities in the table. For each city, the nearest GHCN station
whose ID begins with USW (first-order weather stations) and whose TMAX is
present on at least 95% of days in the window, searching candidates within
100 km in order of distance; if none qualifies, the nearest GHCN station of any
type that qualifies. BA temperature = equal-weight mean of its cities' TMAX on
days with at least half of the cities present.

Hot day: a June to September day whose BA temperature is at or above the 95th
percentile of that BA's June to September daily temperatures over the window.

| BA | Cities (lat, lon) |
|---|---|
| AECI | Springfield MO (37.21, -93.29) |
| AVA | Spokane (47.66, -117.43) |
| AZPS | Phoenix (33.45, -112.07) |
| BANC | Sacramento (38.58, -121.49) |
| BPAT | Portland OR (45.52, -122.68); Seattle (47.61, -122.33); Spokane (47.66, -117.43) |
| CISO | Los Angeles (34.05, -118.24); Riverside (33.95, -117.40); San Diego (32.72, -117.16); San Jose (37.34, -121.89); Fresno (36.74, -119.79) |
| CPLE | Raleigh (35.78, -78.64) |
| CPLW | Asheville (35.60, -82.55) |
| DUK | Charlotte (35.23, -80.84); Greensboro (36.07, -79.79); Greenville SC (34.85, -82.40) |
| EPE | El Paso (31.76, -106.49) |
| ERCO | Dallas (32.78, -96.80); Houston (29.76, -95.37); Austin (30.27, -97.74); San Antonio (29.42, -98.49) |
| FMPP | Orlando (28.54, -81.38) |
| FPC | Orlando (28.54, -81.38); St Petersburg (27.77, -82.64) |
| FPL | Miami (25.76, -80.19); West Palm Beach (26.72, -80.05); Fort Myers (26.64, -81.87) |
| GCPD | Moses Lake (47.13, -119.28) |
| IPCO | Boise (43.62, -116.20) |
| ISNE | Boston (42.36, -71.06); Hartford (41.76, -72.68); Providence (41.82, -71.41) |
| JEA | Jacksonville (30.33, -81.66) |
| LDWP | Los Angeles (34.05, -118.24) |
| LGEE | Louisville (38.25, -85.76); Lexington (38.04, -84.50) |
| MISO | Minneapolis (44.98, -93.27); Detroit (42.33, -83.05); St Louis (38.63, -90.20); Indianapolis (39.77, -86.16); New Orleans (29.95, -90.07); Milwaukee (43.04, -87.91) |
| NEVP | Las Vegas (36.17, -115.14) |
| NWMT | Billings (45.78, -108.50); Missoula (46.87, -114.00); Great Falls (47.50, -111.30) |
| NYIS | New York City (40.71, -74.01); Islip (40.73, -73.21); Albany (42.65, -73.75); Buffalo (42.89, -78.88) |
| PACE | Salt Lake City (40.76, -111.89) |
| PACW | Portland OR (45.52, -122.68); Medford (42.33, -122.87); Yakima (46.60, -120.51) |
| PGE | Portland OR (45.52, -122.68) |
| PJM | Philadelphia (39.95, -75.17); Chicago (41.88, -87.63); Washington DC (38.91, -77.04); Columbus OH (39.96, -83.00); Newark (40.74, -74.17) |
| PNM | Albuquerque (35.08, -106.65) |
| PSCO | Denver (39.74, -104.99) |
| PSEI | Bellevue (47.61, -122.20) |
| SC | Charleston (32.78, -79.93); Myrtle Beach (33.69, -78.89) |
| SCEG | Columbia SC (34.00, -81.03); Charleston (32.78, -79.93) |
| SCL | Seattle (47.61, -122.33) |
| SOCO | Atlanta (33.75, -84.39); Birmingham (33.52, -86.80); Mobile (30.69, -88.04); Savannah (32.08, -81.09) |
| SRP | Phoenix (33.45, -112.07) |
| SWPP | Oklahoma City (35.47, -97.52); Kansas City (39.10, -94.58); Tulsa (36.15, -95.99); Omaha (41.26, -95.93); Wichita (37.69, -97.34) |
| TEC | Tampa (27.95, -82.46) |
| TEPC | Tucson (32.22, -110.97) |
| TPWR | Tacoma (47.25, -122.44) |
| TVA | Nashville (36.16, -86.78); Memphis (35.15, -90.05); Knoxville (35.96, -83.92); Chattanooga (35.05, -85.31) |
| WACM | Denver (39.74, -104.99); Cheyenne (41.14, -104.82) |
| WALC | Phoenix (33.45, -112.07) |

A BA in the sample without a row here (possible only if the coverage rule admits
one not anticipated) gets its largest city, logged as a deviation. BAs in the
secondary sample below 500 MW are not used in the weather analysis.

## Hypotheses (primary; unit of inference = BA)

For each BA: bias_A = median p_d over A-top days; bias_F = median p_d over
F-top days.

- **H1 (the scorecard finding).** bias_A < 0 in a majority of BAs.
  One-sided binomial sign test.
- **H2 (genuine under-forecast of peaks).** bias_F < 0 in a majority of BAs.
  One-sided binomial sign test.
- **H3 (heat).** Within June to September, median p on hot days minus median p
  on other June to September days is negative in a majority of BAs.
  One-sided sign test. Hot days are chosen by observed temperature, which is
  close to but not the same as what was known a day ahead, so H3 mixes the
  operator's load model error with weather-forecast error; the paper says so.
- **H4 (trend).** Median |p| over June to September days in 2023 to 2026 minus
  the same in 2016 to 2019 differs in sign from zero in more BAs than chance:
  two-sided sign test.

Multiplicity: Holm over the four primary p-values at family alpha 0.05. A BA
whose statistic is exactly zero is dropped from that sign test.

## Pre-specified secondary analyses

1. Pooled effects: random-effects (DerSimonian-Laird) means of bias_A, bias_F,
   the H3 difference and the H4 difference, with BA standard errors from a
   moving-block bootstrap over weeks (7-day blocks, 2,000 replicates, seed
   20261118).
2. Selection benchmark: for each BA-year, shuffle the ratios r_d = D*_d / F*_d
   across days (keeping F*_d fixed), rebuild D*_d = F*_d x r, and recompute
   bias_A; 200 shuffles. Under the shuffle the forecast is calibrated up to its
   mean bias, so this gives the bias_A that selection alone produces. Report the
   observed bias_A next to this benchmark for each BA.
3. Mincer-Zarnowitz slope of D* on F* over June to September days per BA;
   slope > 1 means forecast peaks move too little.
4. Robustness: secondary sample; top 10% days instead of 5%; peak-hour error
   e_d instead of p_d; EIA "Demand (MW) (Adjusted)" instead of screened reported
   demand; regional sign test (majority within each EIA region counted once).
5. Heat-wave run length: p by day index within runs of consecutive hot days
   (1, 2, 3+).

## Outputs

out/results.json (every number in the paper comes from it through generated
LaTeX macros), out/ba_table.csv, figures. Code: code/. Weather download script
writes hashes.

## What would change the conclusions

If H1 holds and H2 does not, the public "operators under-forecast peaks" claim
is mostly selection and scorecards should condition on the forecast. If both
hold, operators do under-forecast peaks, and the size of bias_F is the number to
report. Either result is reported.

## Amendment 1 (18 November 2026, after the full results and an internal review)

Bug fixes. None changed the outcome of a hypothesis.
- Block bootstrap: start positions now include the last possible block (was off by one).
- Hot-day runs are counted on the full daily temperature series. Before, they were counted on days with valid load, so a dropped day restarted a run.
- Regional robustness: a region now votes by the majority sign of its BAs, as this plan says. Before, it used the regional median.

Exploratory analyses added after the results, reported as exploratory:
- Share of BA-days with p_d < 0 over all days, to separate hour selection from day selection.
- Bias relative to each BA's overall bias (bias_F - bias_all, bias_A - bias_all), with sign tests.
- Second-highest hourly forecast and demand instead of daily maxima, so a single-hour forecast spike cannot select a day.
- Shuffle benchmark within calendar month.
- Mincer-Zarnowitz slope with year fixed effects, Huber robust regression.
- Day after a hot day against other days; first against third-or-later day within spells of at least three hot days; first and third-or-later days against other summer days.
- Pooled effects without the BAs whose overall bias exceeds 10% in magnitude (FPC, PSEI).
