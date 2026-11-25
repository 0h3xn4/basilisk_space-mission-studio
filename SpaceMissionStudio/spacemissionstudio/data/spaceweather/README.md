# Space weather data

The two files in this folder are real data from their publishers. A
run records the SHA-256 of the file that it used in its provenance.

## `SW-All.txt`

CelesTrak's space weather file (CSSI format, version 1.2).

| | |
|---|---|
| Source | <https://celestrak.org/SpaceData/SW-All.txt> (format: <https://celestrak.org/SpaceData/SpaceWx-format.php>) |
| Updated | 2026-11-19 17:33 UTC |
| Downloaded | 2026-11-19 |
| Observed values | Daily Kp, Ap and F10.7 from 1957-10-01 to 2026-11-18 |
| Daily forecast | CelesTrak's 45-day forecast, to 2027-01-02 |
| Monthly forecast | NOAA's monthly F10.7 forecast, from 2027-02 to 2041-10 |
| Gap | No rows from 2027-01-03 to 2027-01-31. The MSFC prediction below covers these days. |
| Terms | CelesTrak asks only that the URL above is given, so that others can find the data and its documentation. There are no other licensing requirements (Dr. T.S. Kelso, CelesTrak). |

The earlier copies:

| Downloaded | Updated |
|---|---|
| 2026-11-15 | 2026-11-15 |
| 2026-11-10 | 2026-11-10 |
| 2026-10-26 | 2026-10-25 |
| 2026-10-19 | 2026-10-19 |
| 2026-10-12 | 2026-10-12 |
| From the `spaceweather` Python package, version 0.4.2, which has CelesTrak's permission to copy it | 2025-07-21 |

A newer copy replaces this one automatically
(`engine/spaceweather.py`). You get a newer copy, with your consent,
from the card **Fetch or update reference data?** on **Home**, or from
the **Reference data** window.

## `nov2026f10-prd.txt`

The solar cycle prediction of NASA Marshall Space Flight Center (MSFC),
November 2026. Its title is "Table 3: estimates of 13-month smoothed
solar activity for the balance of cycle 25, with a mean cycle for cycle
26".

| | |
|---|---|
| Source | <https://www.nasa.gov/solar-cycle-progression-and-forecast/> (this issue: `wp-content/uploads/2026/11/nov2026f10-prd.txt`) |
| Downloaded | 2026-11-16 |
| Contents | Monthly F10.7 and Ap at the 95th, 50th and 5th percentiles, from 2026-05 to 2041-10 |
| Replaces | The October 2026 issue (`oct2026f10-prd.txt`), in the app from 2.0.0 to 2.8.0 |
| Terms | A NASA work, so not subject to copyright in the US |

ESA's guideline EOP-FM/2024-07-177 (AD10), Sec. 5.9, specifies MSFC's
prediction for future solar activity:

- the 95th percentile for operations budgets;
- the 50th percentile for the end of life;
- NRLMSISE-00;
- the last 132 months repeated after the end of the file.

A study can use its own MSFC file: set **MSFC prediction** on the
**Scenario › Environment** page.

## Changes to the files

The two files are the same as the published originals, except for
whitespace that the pre-commit hooks of this repository remove:

- the line endings are LF, not CRLF;
- two header lines have no trailing spaces: one comment line of
  `SW-All.txt`, and the percentile header of `nov2026f10-prd.txt`.

No value changed.
