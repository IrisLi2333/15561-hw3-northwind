"""Q1 analysis: Northwind's performance and what drives its growth.

Run ``python src/q1_overview.py`` from the project root; it writes
``docs/data/q1.json``.
"""
import math

import pandas as pd

import northwind as nw

LAST_FULL_QUARTER_END = pd.Timestamp("1998-04-01")   # 1998 Q2 has orders to 6 May only
LATE_COHORT_START = "1997Q3"                          # later cohorts are grouped, as each is small
LATE_COHORT_LABEL = "1997 Q3 or later"


def headline(window_lines):
    """Compute revenue and its building blocks for one period.

    Args:
        window_lines (pandas.DataFrame): Order lines of one period.

    Returns:
        dict[str, float]: ``revenue``, ``orders``, ``customers``,
        ``aov`` (average order value), ``orders_per_customer``,
        ``lines_per_order`` and ``line_value``.
    """
    revenue = window_lines.Revenue.sum()
    orders = window_lines.OrderID.nunique()
    customers = window_lines.CustomerID.nunique()
    n_lines = len(window_lines)
    return {
        "revenue": revenue,
        "orders": orders,
        "customers": customers,
        "aov": revenue / orders,                       # average order value
        "orders_per_customer": orders / customers,
        "lines_per_order": n_lines / orders,
        "line_value": revenue / n_lines,               # average value of one order line
    }


def kpis(prior, current):
    """Compare the headline measures across the two periods.

    Args:
        prior (pandas.DataFrame): Order lines of the prior period.
        current (pandas.DataFrame): Order lines of the current period.

    Returns:
        dict[str, dict]: For each measure from :func:`headline`, its
        ``prior`` and ``current`` values and ``growth`` ratio.
    """
    a, b = headline(prior), headline(current)
    return {name: {"prior": a[name], "current": b[name], "growth": nw.pct_change(b[name], a[name])}
            for name in a}


def driver_split(k):
    """Attribute revenue growth to its multiplicative drivers.

    Revenue = customers × orders per customer × average order value, so
    the log of the revenue ratio is the sum of the drivers' log ratios.
    Average order value splits the same way into lines per order × line
    value.

    Args:
        k (dict): Output of :func:`kpis`.

    Returns:
        dict[str, float]: Each driver's share of revenue log growth.
        ``customers``, ``orders_per_customer`` and ``aov`` sum to 1;
        ``lines_per_order`` and ``line_value`` sum to ``aov``.

    Raises:
        AssertionError: If the shares do not add up.
    """
    def log_ratio(name):
        """Return the log of a measure's current-to-prior ratio.

        Args:
            name (str): Measure key in ``k``.

        Returns:
            float: ``log(current / prior)``.
        """
        return math.log(k[name]["current"] / k[name]["prior"])

    total = log_ratio("revenue")
    parts = {name: log_ratio(name) / total
             for name in ["customers", "orders_per_customer", "aov", "lines_per_order", "line_value"]}
    assert abs(parts["customers"] + parts["orders_per_customer"] + parts["aov"] - 1) < 1e-9
    assert abs(parts["lines_per_order"] + parts["line_value"] - parts["aov"]) < 1e-9
    return parts


def monthly_trend(lines):
    """Summarise revenue by month, July 1996 to April 1998.

    Args:
        lines (pandas.DataFrame): All order lines.

    Returns:
        pandas.DataFrame: One row per month (index ``'YYYY-MM'``) with
        ``revenue``, ``orders``, ``rolling_3m`` (3-month mean revenue,
        NaN for the first two months) and ``largest_order`` (revenue of
        the month's biggest order).
    """
    trend_lines = lines[lines.OrderDate < nw.TREND_END]
    monthly = trend_lines.groupby("Month").agg(revenue=("Revenue", "sum"), orders=("OrderID", "nunique"))
    monthly["rolling_3m"] = monthly.revenue.rolling(3).mean()
    monthly["largest_order"] = trend_lines.groupby(["Month", "OrderID"]).Revenue.sum().groupby("Month").max()
    monthly.index = monthly.index.astype(str)
    return monthly


def contribution(prior, current, key, total_change):
    """Measure each group's contribution to the revenue increase.

    Args:
        prior (pandas.DataFrame): Order lines of the prior period.
        current (pandas.DataFrame): Order lines of the current period.
        key (str): Column to group by.
        total_change (float): Total revenue change in US$.

    Returns:
        pandas.DataFrame: Output of :func:`northwind.compare` plus
        ``share_of_increase``.

    Raises:
        AssertionError: If the group changes do not sum to
            ``total_change``.
    """
    table = nw.compare(prior, current, key)
    table["share_of_increase"] = table.change / total_change
    assert abs(table.change.sum() - total_change) < 0.01, f"{key} contributions must sum to the total"
    return table


def breadth(table):
    """Count how many groups grew or declined.

    Args:
        table (pandas.DataFrame): Table with a ``change`` column.

    Returns:
        dict: ``items``, ``grew``, ``declined`` and ``share_grew``.
    """
    return {
        "items": len(table),
        "grew": int((table.change > 0).sum()),
        "declined": int((table.change < 0).sum()),
        "share_grew": float((table.change > 0).mean()),
    }


def concentration(window_lines):
    """Measure customer revenue concentration in one period.

    Args:
        window_lines (pandas.DataFrame): Order lines of one period.

    Returns:
        dict: ``customers``, ``top10_share``, ``top1_share``,
        ``customers_for_80pct``, ``share_of_customers_for_80pct`` and
        ``curve``, the Pareto points (cumulative customer share and
        cumulative revenue share), largest customer first.
    """
    revenue = window_lines.groupby("CustomerID").Revenue.sum().sort_values(ascending=False)
    cumulative = revenue.cumsum() / revenue.sum()
    n = len(revenue)
    customers_for_80 = int((cumulative < 0.8).sum()) + 1
    return {
        "customers": n,
        "top10_share": float(revenue.head(10).sum() / revenue.sum()),
        "top1_share": float(revenue.iloc[0] / revenue.sum()),
        "customers_for_80pct": customers_for_80,
        "share_of_customers_for_80pct": customers_for_80 / n,
        "curve": [{"customer_share": (i + 1) / n, "revenue_share": float(c)}
                  for i, c in enumerate(cumulative)],
    }


def cohort_revenue(lines):
    """Split quarterly revenue by customer cohort.

    Covers complete quarters only, before ``LAST_FULL_QUARTER_END``.
    Cohorts from ``LATE_COHORT_START`` onward are grouped into one.

    Args:
        lines (pandas.DataFrame): All order lines.

    Returns:
        dict: ``quarters`` (labels such as ``'1996 Q3'``), ``cohorts``
        (each with ``cohort``, ``customers`` and quarterly ``revenue``)
        and ``last_quarter_share`` (each cohort's share of the last
        quarter's revenue).

    Raises:
        AssertionError: If the split does not sum to total revenue.
    """
    full = lines[lines.OrderDate < LAST_FULL_QUARTER_END].copy()
    full["Quarter"] = full.OrderDate.dt.to_period("Q")
    first_quarter = lines.groupby("CustomerID").OrderDate.min().dt.to_period("Q")
    late = first_quarter >= pd.Period(LATE_COHORT_START, freq="Q")
    labels = first_quarter.astype(str).str.replace("Q", " Q")
    labels[late] = LATE_COHORT_LABEL
    full["Cohort"] = full.CustomerID.map(labels)
    table = full.pivot_table(index="Cohort", columns="Quarter", values="Revenue", aggfunc="sum", fill_value=0.0)
    table = table.reindex(sorted(table.index, key=lambda c: (c == LATE_COHORT_LABEL, c)))
    sizes = labels.value_counts()
    assert abs(table.values.sum() - full.Revenue.sum()) < 0.01
    return {
        "quarters": [str(q).replace("Q", " Q") for q in table.columns],
        "cohorts": [{"cohort": c, "customers": int(sizes[c]), "revenue": [float(v) for v in row]}
                    for c, row in table.iterrows()],
        "last_quarter_share": {c: float(table.loc[c].iloc[-1] / table.iloc[:, -1].sum()) for c in table.index},
    }


def waterfalls(result, markets, categories):
    """Build three waterfall views of the revenue increase.

    Args:
        result (dict): Q1 result with ``kpis``, ``total_change`` and
            ``driver_split``.
        markets (pandas.DataFrame): Market contributions, largest first.
        categories (pandas.DataFrame): Category contributions, largest
            first.

    Returns:
        dict[str, list[dict]]: Bars for ``drivers``, ``markets`` (top
        six, other growing markets, declining markets) and
        ``categories``.
    """
    k, total = result["kpis"], result["total_change"]
    start, split = k["revenue"]["prior"], result["driver_split"]
    drivers = [("More active customers", split["customers"] * total),
               ("More orders per customer", split["orders_per_customer"] * total),
               ("Higher average order value", split["aov"] * total)]
    top = markets.head(6)
    rest = markets.iloc[6:]
    rest_up = rest[rest.change > 0]
    down = markets[markets.change < 0]
    by_market = [(name, row.change) for name, row in top.iterrows()]
    by_market.append((f"{len(rest_up)} other growing markets", rest_up.change.sum()))
    by_market.append((f"{len(down)} declining markets", down.change.sum()))
    by_category = [(name, row.change) for name, row in categories.iterrows()]
    return {
        "drivers": nw.waterfall(nw.PRIOR_LABEL, start, drivers, nw.CURRENT_LABEL),
        "markets": nw.waterfall(nw.PRIOR_LABEL, start, by_market, nw.CURRENT_LABEL),
        "categories": nw.waterfall(nw.PRIOR_LABEL, start, by_category, nw.CURRENT_LABEL),
    }


def narrate(result, markets, categories):
    """Write chart titles, legends, sources and the Q1 conclusions.

    Args:
        result (dict): Q1 result built in :func:`main`.
        markets (pandas.DataFrame): Market contributions, largest first.
        categories (pandas.DataFrame): Category contributions, largest
            first.

    Returns:
        dict: Text keyed by chart (``monthly``, ``bridge``,
        ``cohorts``, ``pareto``), plus ``finding`` and
        ``implication``.
    """
    k, split, b = result["kpis"], result["driver_split"], result["breadth"]
    conc_a, conc_b = result["concentration"]["prior"], result["concentration"]["current"]
    monthly = result["monthly"]
    top3 = nw.join_names(markets.index[:3])
    windows = f"{nw.PRIOR_LABEL} vs {nw.CURRENT_LABEL}"
    fastest = categories.growth.idxmax()
    return {
        "monthly": {
            "title": f"Monthly revenue climbed from {nw.usd_k(monthly[0]['revenue'])} in July 1996 to "
                     f"{nw.usd_k(monthly[-1]['revenue'])} in April 1998",
            "sub": nw.legend("Net revenue per month, in US$ thousands, July 1996 to April 1998",
                              "Blue columns: revenue in the month",
                              "Orange line: 3-month rolling average"),
            "src": f"Column and line chart. Data: Orders, Order Details. n = {len(monthly)} months",
        },
        "bridge": {
            "drivers": {
                "title": f"Customers ordering more often explain {nw.pct(split['orders_per_customer'])} "
                         f"of the revenue increase",
                "sub": nw.legend(f"Change in net revenue by driver, in US$ thousands, {windows}",
                                  "Revenue = active customers × orders per customer × average order value",
                                  "Dark blue: total revenue in each period",
                                  "Blue: increase from each driver"),
            },
            "markets": {
                "title": f"{top3} brought {nw.pct(result['top3_market_share_of_increase'])} of the increase; "
                         f"{b['markets']['grew']} of {b['markets']['items']} markets grew",
                "sub": nw.legend(f"Change in net revenue by customer country, in US$ thousands, {windows}",
                                  "Dark blue: total revenue in each period",
                                  "Blue: markets that grew",
                                  "Orange: markets that declined"),
            },
            "categories": {
                "title": f"All {b['categories']['grew']} categories grew; {categories.index[0]} added the most "
                         f"and {fastest} grew fastest ({nw.pct(categories.growth[fastest], signed=True)})",
                "sub": nw.legend(f"Change in net revenue by product category, in US$ thousands, {windows}",
                                  "Dark blue: total revenue in each period",
                                  "Blue: categories that grew"),
            },
            "src": "Waterfall chart. Data: Orders, Order Details, Customers, Product, Categories",
        },
        "cohorts": {
            "title": f"Customers won in 1996 still brought "
                     f"{nw.pct(sum(v for k_, v in result['cohort_revenue']['last_quarter_share'].items() if k_.startswith('1996')))} "
                     f"of revenue in {result['cohort_revenue']['quarters'][-1]}",
            "sub": nw.legend(f"Net revenue per complete quarter, in US$ thousands, "
                             f"{result['cohort_revenue']['quarters'][0]} to {result['cohort_revenue']['quarters'][-1]}",
                             *[f"{name}: {c['cohort']} cohort ({c['customers']} customers)" for name, c in
                               zip(["Blue", "Orange", "Dark blue", "Light orange", "Light blue"],
                                   result["cohort_revenue"]["cohorts"])]),
            "src": f"Stacked column chart. Data: Orders, Order Details. "
                   f"n = {sum(c['customers'] for c in result['cohort_revenue']['cohorts'])} customers",
        },
        "pareto": {
            "title": f"The top 10 customers bring {nw.pct(conc_b['top10_share'], digits=1)} of revenue, "
                     f"up from {nw.pct(conc_a['top10_share'], digits=1)}",
            "sub": nw.legend("Cumulative share of net revenue, customers ranked from largest to smallest",
                              f"Blue line: {nw.CURRENT_LABEL}",
                              f"Light blue line: {nw.PRIOR_LABEL}",
                              "Orange dot: where the top 10 customers end",
                              "Dotted diagonal: every customer the same size"),
            "src": f"Pareto curve. Data: Orders, Order Details. n = {conc_b['customers']} customers",
        },
        "finding": (
            f"Net revenue grew {nw.pct(k['revenue']['growth'])} to {nw.usd_k(k['revenue']['current'])}. "
            f"Purchase frequency drove it: orders per customer rose from {k['orders_per_customer']['prior']:.1f} "
            f"to {k['orders_per_customer']['current']:.1f}, which explains {nw.pct(split['orders_per_customer'])} "
            f"of the increase, while the customer base and average order value each grew about "
            f"{nw.pct(k['customers']['growth'])}. The growth is broad: all {b['categories']['grew']} categories, "
            f"{b['markets']['grew']} of {b['markets']['items']} markets and {b['customers']['grew']} of "
            f"{b['customers']['items']} customers grew. Concentration edged up, with the top 10 customers at "
            f"{nw.pct(conc_b['top10_share'], digits=1)} of revenue and {top3} supplying "
            f"{nw.pct(result['top3_market_share_of_increase'])} of the increase."
        ),
        "implication": (
            "The growth rests on established customers buying more often, which gives management a solid base "
            "for planning. The main exposure is concentration: about half of "
            "revenue rests on ten accounts and three markets carry most of the increase. Assign clear ownership "
            "of the top accounts and track orders per customer as the leading indicator of momentum."
        ),
    }


def method():
    """List the definitions shown in the Q1 method card.

    Args:
        None.

    Returns:
        list[list[str]]: ``[term, definition]`` pairs.
    """
    return [
        ["Comparison periods", f"{nw.PRIOR_LABEL} against {nw.CURRENT_LABEL}. The data spans 22 complete months, "
         "two short of the 24 a full-year comparison needs. July to April is the longest pair of periods covering "
         "the same months of the year, which holds seasonal effects equal."],
        ["Net revenue", "Unit price × quantity × (1 − discount), summed over order lines. Freight is excluded."],
        ["Revenue drivers", "Revenue = active customers × orders per customer × average order value. An active "
         "customer placed at least one order in the period. Orders per customer = orders ÷ active customers. "
         "Average order value = net revenue ÷ orders."],
        ["Driver contribution", "A driver's share of the increase = log of its growth ratio ÷ log of the revenue "
         "growth ratio. Logs turn the product into a sum, so the three shares add to 100%; each share × the total "
         "increase gives the driver's dollar amount."],
        ["Waterfall chart", "Starts from the earlier period's revenue, adds each component's change as a step, "
         "and ends at the later period's revenue."],
        ["Customer cohort", "Customers grouped by the quarter of their first order in the data. The 1996 Q3 "
         "cohort includes customers who started before the data begins."],
        ["Pareto curve", "Customers ranked from largest to smallest. The curve plots the cumulative share of "
         "revenue against the cumulative share of customers; the more it bows upward, the more concentrated "
         "revenue is."],
    ]


def add_notes(text, result, markets, categories):
    """Add a description and a takeaway to each Q1 chart.

    Args:
        text (dict): Output of :func:`narrate`; updated in place.
        result (dict): Q1 result built in :func:`main`.
        markets (pandas.DataFrame): Market contributions, largest first.
        categories (pandas.DataFrame): Category contributions, largest
            first.

    Returns:
        None. Adds ``about`` and ``takeaway`` entries to ``text``.
    """
    k, split, total = result["kpis"], result["driver_split"], result["total_change"]
    b = result["breadth"]
    m = pd.DataFrame(result["monthly"])
    rolled = m.dropna(subset=["rolling_3m"])
    y97 = m[m.month.str.startswith("1997")].revenue.mean()
    recent = m[m.month >= "1998-01"]
    record = ("Each month from January to April 1998 set a new high. "
              if recent.revenue.min() > m[m.month < "1998-01"].revenue.max() else "")
    peak = (m.largest_order / m.revenue).max()
    text["monthly"]["about"] = ("Net revenue for each month, with a 3-month rolling average that smooths out "
                                "single large orders.")
    text["monthly"]["takeaway"] = (
        f"The 3-month average rose from {nw.usd_k(rolled.rolling_3m.iloc[0])} in "
        f"{nw.month_name(rolled.month.iloc[0])} to {nw.usd_k(rolled.rolling_3m.iloc[-1])} in "
        f"{nw.month_name(rolled.month.iloc[-1])}. {record}January to April 1998 averaged "
        f"{nw.usd_k(recent.revenue.mean())} a month, {recent.revenue.mean() / y97:.1f}× the 1997 monthly average. "
        f"No single order exceeded {nw.pct(peak)} of its month's revenue, so the climb comes from many orders.")

    top3m, top3c = markets.head(3), categories.head(3)
    down = markets[markets.change < 0]
    smallest = categories.change.idxmin()
    bridge = text["bridge"]
    bridge["about"] = "A waterfall chart of the revenue increase. Switch the view to see it by driver, market or category."
    bridge["drivers"]["takeaway"] = (
        f"Purchase frequency did most of the work: orders per customer rose from "
        f"{k['orders_per_customer']['prior']:.1f} to {k['orders_per_customer']['current']:.1f}, adding "
        f"{nw.usd_k(split['orders_per_customer'] * total)}. Active customers grew from {k['customers']['prior']} to "
        f"{k['customers']['current']} and average order value from ${k['aov']['prior']:,.0f} to "
        f"${k['aov']['current']:,.0f}, together adding {nw.usd_k((split['customers'] + split['aov']) * total)}.")
    bridge["markets"]["takeaway"] = (
        f"{nw.join_names(top3m.index)} added {nw.usd_k(top3m.change.sum())}, "
        f"{nw.pct(top3m.change.sum() / total)} of the increase. {b['markets']['grew']} of {b['markets']['items']} "
        f"markets grew. The {len(down)} declining markets lost {nw.usd_k(abs(down.change.sum()))} combined, "
        f"{nw.pct(abs(down.change.sum()) / total, digits=1)} of the increase.")
    bridge["categories"]["takeaway"] = (
        f"Every category grew. {nw.join_names(top3c.index)} added {nw.usd_k(top3c.change.sum())}, "
        f"{nw.pct(top3c.change.sum() / total)} of the increase. The smallest gain, {smallest}, was still "
        f"{nw.usd_k(categories.change[smallest])} ({nw.pct(categories.growth[smallest], signed=True)}).")

    co = result["cohort_revenue"]
    share = co["last_quarter_share"]
    early = [c for c in share if c.startswith("1996")]
    first = co["cohorts"][0]
    late = co["cohorts"][-1]
    text["cohorts"]["about"] = ("Revenue in each complete quarter, split by when each customer placed their first "
                                "order.")
    text["cohorts"]["takeaway"] = (
        f"Customers won in 1996 brought {nw.pct(sum(share[c] for c in early))} of revenue in {co['quarters'][-1]}. "
        f"The {first['cohort']} cohort's quarterly revenue rose from {nw.usd_k(first['revenue'][0])} to "
        f"{nw.usd_k(first['revenue'][-1])}, {first['revenue'][-1] / first['revenue'][0]:.1f}× in "
        f"{len(co['quarters']) - 1} quarters, while the {late['customers']} customers who joined from 1997 Q3 onward "
        f"brought {nw.pct(share[late['cohort']])}. Growth came from the established base buying more, which matches "
        "the driver split in Figure 1.2.")

    a, c = result["concentration"]["prior"], result["concentration"]["current"]
    trend = ("Revenue is concentrating gradually as the business grows."
             if c["top10_share"] > a["top10_share"] else "Concentration held steady as the business grew.")
    text["pareto"]["about"] = "A Pareto curve of customer revenue in both periods."
    text["pareto"]["takeaway"] = (
        f"{c['customers_for_80pct']} of {c['customers']} customers ({nw.pct(c['share_of_customers_for_80pct'])}) "
        f"bring 80% of revenue. The top 10 customers' share rose from {nw.pct(a['top10_share'], digits=1)} to "
        f"{nw.pct(c['top10_share'], digits=1)}, and the largest customer's from {nw.pct(a['top1_share'], digits=1)} "
        f"to {nw.pct(c['top1_share'], digits=1)}. {trend}")


def main():
    """Run the Q1 analysis.

    Args:
        None.

    Returns:
        None. Writes ``docs/data/q1.json`` and prints a summary.
    """
    lines, _ = nw.load()
    prior, current = nw.both_windows(lines)
    k = kpis(prior, current)
    total_change = k["revenue"]["current"] - k["revenue"]["prior"]

    markets = contribution(prior, current, "Country", total_change)
    categories = contribution(prior, current, "CategoryName", total_change)
    customers = contribution(prior, current, "CompanyName", total_change)
    top3_markets = float(markets.share_of_increase.head(3).sum())

    result = {
        "windows": {"prior": nw.PRIOR_LABEL, "current": nw.CURRENT_LABEL},
        "kpis": k,
        "total_change": total_change,
        "driver_split": driver_split(k),
        "monthly": nw.records(monthly_trend(lines), "month"),
        "markets": nw.records(markets, "market"),
        "categories": nw.records(categories, "category"),
        "top3_market_share_of_increase": top3_markets,
        "breadth": {"markets": breadth(markets), "categories": breadth(categories),
                    "customers": breadth(customers)},
        "concentration": {"prior": concentration(prior), "current": concentration(current)},
        "cohort_revenue": cohort_revenue(lines),
    }
    result["waterfalls"] = waterfalls(result, markets, categories)
    result["text"] = narrate(result, markets, categories)
    add_notes(result["text"], result, markets, categories)
    result["text"]["method"] = method()
    nw.save("q1", result)

    print(f"\nQ1  {nw.PRIOR_LABEL} vs {nw.CURRENT_LABEL}")
    for name, v in k.items():
        print(f"  {name:20s} {v['prior']:>12,.2f} -> {v['current']:>12,.2f}  ({v['growth']:+.1%})")
    print("  driver split:", {n: f"{s:.0%}" for n, s in result["driver_split"].items()})
    print("  breadth:", {n: f"{b['grew']}/{b['items']}" for n, b in result["breadth"].items()})
    print(f"  top 3 markets = {top3_markets:.0%} of increase")
    for name in ["prior", "current"]:
        c = result["concentration"][name]
        print(f"  concentration {name}: top10 {c['top10_share']:.1%}, top1 {c['top1_share']:.1%}, "
              f"80% from {c['customers_for_80pct']} of {c['customers']}")
    print("  cohort share of last full quarter:",
          {c: f"{v:.0%}" for c, v in result["cohort_revenue"]["last_quarter_share"].items()})
    print(categories.round(2).to_string())
    print(pd.DataFrame(result["monthly"]).round(0).to_string())


if __name__ == "__main__":
    main()
