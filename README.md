# Growing Fast, Growing Well? Northwind's Growth Quality and Strategic Priorities

MIT 15.561, Fall 2026, Homework 3: AI-Assisted Business Data Analysis.

**Webpage:** <https://IrisLi2333.github.io/15561-hw3-northwind/>

This repository contains the Python analysis behind the webpage. It answers three management questions about Northwind Traders:

1. **Diagnose:** How is Northwind performing overall, what is driving its growth, and how broad-based and sustainable is that growth?
2. **Prioritize:** Given a lean nine-person team, which markets and product categories should Northwind prioritize to sustain its growth?
3. **Protect:** Beneath the headline growth, which products and markets are losing ground, and how well is Northwind retaining the customers it has won?

Every number, chart and table on the webpage is produced by the Python scripts in `src/` from the Northwind dataset in `data/raw/`.

## Reproduce the results

### 1. Requirements

- Python 3.11 or later (developed with Python 3.14)
- The packages in `requirements.txt`: pandas and openpyxl

```bash
git clone https://github.com/IrisLi2333/15561-hw3-northwind.git
cd 15561-hw3-northwind
python -m pip install -r requirements.txt
```

### 2. Data

The analysis uses the Northwind dataset provided for the course, an Excel export of
[this Google Sheet](https://docs.google.com/spreadsheets/d/1mD4Hn4NZdJlXMC4EJcSp27vg-_jbxUYJ95vQvMbSpVM/edit).
The exact file analysed is committed at `data/raw/northwind.xlsx`, so no download is needed.

To confirm you have the same file, its SHA-256 checksum is:

```
31bf1a58fb29e91c56ba2b5943100cd2372605022c840690ce6477eb5ee4564a
```

### 3. Run the analysis

From the repository root:

```bash
python src/run_all.py
```

This runs the three analyses in order and writes one data file per question:

| Script | Question | Output |
|---|---|---|
| `src/q1_overview.py` | 01 Diagnose | `docs/data/q1.json` |
| `src/q2_priorities.py` | 02 Prioritize | `docs/data/q2.json` |
| `src/q3_risks.py` | 03 Protect | `docs/data/q3.json` |

Each script can also be run on its own, for example `python src/q1_overview.py`. Each one prints a summary of its key numbers to the console.

The scripts check their own results and stop with an error if a check fails:
- Net revenue for all orders must equal **$1,265,793.04**.
- Joining the tables must not duplicate or drop any order line.
- Every breakdown (by market, category, customer group, employee, or market and category) must add back to its total.

### 4. View the webpage

The webpage reads the three data files, so it has to be served over HTTP rather than opened as a file:

```bash
python -m http.server 8000 --directory docs
```

Then open <http://localhost:8000>. The published copy at the link above is the same `docs/` folder, served by GitHub Pages.

## Where each result comes from

All text that states a number on the webpage (chart titles, takeaways, findings and the headline figures) is written by the Python scripts and stored in the `text` field of each data file. The webpage only displays it.

| Webpage element | Python function | Data field |
|---|---|---|
| 01 headline figures | `q1_overview.headline`, `kpis` | `q1.json` → `kpis` |
| Figure 1.1 Monthly revenue | `q1_overview.monthly_trend` | `q1.json` → `monthly` |
| Figure 1.2 Revenue bridge (drivers, markets, categories) | `q1_overview.driver_split`, `contribution`, `waterfalls` | `q1.json` → `waterfalls` |
| Figure 1.3 Pareto curve | `q1_overview.concentration` | `q1.json` → `concentration` |
| Figure 1.4 Revenue by customer cohort | `q1_overview.cohort_revenue` | `q1.json` → `cohort_revenue` |
| Figure 2.1 Market portfolio | `q2_priorities.portfolio`, `add_quadrants`, `add_score`, `top_customer_share` | `q2.json` → `markets`, `market_medians` |
| Figure 2.2 Category dumbbell | `q2_priorities.portfolio`, `add_quadrants` | `q2.json` → `categories` |
| Figure 2.3 Team workload table | `q2_priorities.team_workload`, `team_summary` | `q2.json` → `team`, `team_summary` |
| Figure 2.4 Market × category heatmap | `q2_priorities.market_category_grid`, `cross_sell_gaps` | `q2.json` → `grid`, `cross_sell_gaps` |
| Figure 3.1 Customer revenue bridge | `q3_risks.customer_bridge` | `q3.json` → `waterfall`, `retained` |
| Figure 3.2 Product gains and declines | `q3_risks.product_view`, `product_summary` | `q3.json` → `product_movers`, `product_summary` |
| Figure 3.3 Overdue customers and table | `q3_risks.order_rhythm`, `trailing_revenue` | `q3.json` → `rhythm` |
| Figure 3.4 Declining markets | `q3_risks.market_decline`, `largest_movers_in` | `q3.json` → `declining_markets`, `declining_market_customers` |
| Figure 3.5 Cohort retention | `q3_risks.cohort_retention` | `q3.json` → `cohort_retention` |
| Titles, legends, takeaways, findings, definitions | `narrate`, `add_notes`, `method` in each script | `q1.json`, `q2.json`, `q3.json` → `text` |

Shared definitions live in `src/northwind.py`:
- net revenue: unit price × quantity × (1 − discount), with freight excluded
- the comparison periods: July 1996 to April 1997 against July 1997 to April 1998
- the market: the customer's country

The method card on each page of the webpage defines every derived measure.

## Repository structure

```
data/raw/northwind.xlsx      Northwind dataset provided for the course
src/northwind.py             Shared loading, definitions and formatting helpers
src/q1_overview.py           Question 1 analysis
src/q2_priorities.py         Question 2 analysis
src/q3_risks.py              Question 3 analysis
src/run_all.py               Runs all three analyses
docs/index.html              The webpage (served by GitHub Pages)
docs/data/                   Analysis output read by the webpage
docs/assets/                 Webpage styles and chart drawing
requirements.txt             Python packages
THIRD_PARTY_NOTICES.md       Credits and licences for adapted material
```

## Code documentation

Every module and function in `src/` has a docstring in Google style. The docstrings were generated with the course's SKILLS.md (the `python-docstrings` skill) through Claude Code. Each one gives a one-line summary, one line per parameter, and the return value.

## Language note

All data analysis is written in Python. The files in `docs/` are the webpage itself: HTML and CSS for layout, and JavaScript that draws the charts from the Python output without computing anything.

## Credits

The chart style is adapted from [Lieflat Charts](https://github.com/larashero3-dotcom/lieflat-charts) under the PolyForm Noncommercial License 1.0.0. See `THIRD_PARTY_NOTICES.md`.
