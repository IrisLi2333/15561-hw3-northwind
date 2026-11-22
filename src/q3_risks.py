"""Q3 analysis: products, markets and customers where growth is exposed.

Run ``python src/q3_risks.py`` from the project root; it writes
``docs/data/q3.json``.
"""
import pandas as pd

import northwind as nw

OVERDUE_MULTIPLE = 2      # overdue when days since last order exceed 2x the customer's usual gap
MIN_ORDERS_FOR_RHYTHM = 3  # a usual gap needs at least two intervals
MIN_COHORT_SIZE = 8        # smaller cohorts are too small to read as a rate


# --- Customers --------------------------------------------------------------
def customer_bridge(prior, current):
    """Classify customers and split the revenue change by group.

    New: no prior revenue. Lost: no current revenue. Contraction:
    revenue fell. Expansion: every other customer, including any whose
    revenue was unchanged.

    Args:
        prior (pandas.DataFrame): Order lines of the prior period.
        current (pandas.DataFrame): Order lines of the current period.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: Revenue per customer
        with a ``segment`` column; and ``customers``, ``change``,
        ``prior`` and ``current`` per segment.

    Raises:
        AssertionError: If the segment changes do not sum to the total
            change.
    """
    table = nw.compare(prior, current, "CustomerID")
    table["segment"] = "Expansion"
    table.loc[table.change < 0, "segment"] = "Contraction"
    table.loc[table.prior == 0, "segment"] = "New"
    table.loc[table.current == 0, "segment"] = "Lost"
    bridge = table.groupby("segment").agg(customers=("change", "size"), change=("change", "sum"),
                                          prior=("prior", "sum"), current=("current", "sum"))
    bridge = bridge.reindex(["New", "Expansion", "Contraction", "Lost"]).fillna(0)
    assert abs(bridge.change.sum() - (current.Revenue.sum() - prior.Revenue.sum())) < 0.01
    return table, bridge


def retained_customer_metrics(table):
    """Measure how prior-period customers behaved in the current period.

    Args:
        table (pandas.DataFrame): Per-customer table from
            :func:`customer_bridge`.

    Returns:
        dict: ``prior_customers``, ``retained_customers``,
        ``contracting_customers`` and
        ``share_of_retained_contracting``.
    """
    base = table[table.prior > 0]
    kept = base[base.current > 0]
    return {
        "prior_customers": len(base),
        "retained_customers": len(kept),
        "contracting_customers": int((kept.change < 0).sum()),
        "share_of_retained_contracting": float((kept.change < 0).mean()),
    }


def order_rhythm(orders, names):
    """Measure each customer's usual order gap and how overdue they are.

    Args:
        orders (pandas.DataFrame): Orders sheet with ``CustomerID`` and
            ``OrderDate``.
        names (pandas.Series): Company name per customer ID.

    Returns:
        pandas.DataFrame: Per customer, ``orders``, ``last_order``,
        ``median_gap`` (days), ``days_since_last`` (to ``DATA_END``),
        ``overdue_ratio``, ``status`` and ``customer``.
    """
    dates = orders.sort_values("OrderDate").groupby("CustomerID").OrderDate
    gaps = dates.diff().dt.days.dropna()
    table = pd.DataFrame({
        "orders": dates.size(),
        "last_order": dates.max(),
        "median_gap": gaps.groupby(orders.sort_values("OrderDate").CustomerID).median(),
    })
    table["days_since_last"] = (nw.DATA_END - table.last_order).dt.days
    table["overdue_ratio"] = table.days_since_last / table.median_gap
    has_rhythm = table.orders >= MIN_ORDERS_FOR_RHYTHM
    table["status"] = "On rhythm"
    table.loc[~has_rhythm, "status"] = "Too few orders"
    table.loc[has_rhythm & (table.overdue_ratio > OVERDUE_MULTIPLE), "status"] = "Overdue"
    table["customer"] = names
    return table


def trailing_revenue(lines, days=365):
    """Sum each customer's revenue in the period before the data cutoff.

    Args:
        lines (pandas.DataFrame): All order lines.
        days (int): Length of the trailing period in days.

    Returns:
        pandas.Series: Net revenue per customer ID in the ``days`` days
        up to ``DATA_END``; customers with no orders then are absent.
    """
    recent = lines[lines.OrderDate > nw.DATA_END - pd.Timedelta(days=days)]
    return recent.groupby("CustomerID").Revenue.sum()


def cohort_retention(orders):
    """Compute quarterly retention by first-order cohort.

    Args:
        orders (pandas.DataFrame): Orders sheet.

    Returns:
        dict: ``typical_retention`` (mean rate over complete later
        quarters of cohorts with at least ``MIN_COHORT_SIZE``
        customers), ``min_cohort_size``, ``shown`` cohorts,
        ``partial_offsets`` (each cohort's offset that falls in the
        partial last quarter) and ``cohorts`` (size and retention by
        quarter offset; offset 0 is 1.0).
    """
    data = orders[["CustomerID", "OrderDate"]].copy()
    data["quarter"] = data.OrderDate.dt.to_period("Q")
    data["cohort"] = data.groupby("CustomerID").quarter.transform("min")
    data["offset"] = (data.quarter - data.cohort).apply(lambda d: d.n)
    active = data.groupby(["cohort", "offset"]).CustomerID.nunique().unstack()
    size = active[0]
    rate = active.div(size, axis=0)
    quarters = sorted(data.quarter.unique())
    last = quarters[-1]                                   # 1998Q2, partial
    shown = [c for c in rate.index if size[c] >= MIN_COHORT_SIZE]
    complete = [rate.loc[c, o] for c in shown for o in rate.columns
                if o >= 1 and pd.notna(rate.loc[c, o]) and c + o != last]
    return {
        "typical_retention": float(sum(complete) / len(complete)),
        "min_cohort_size": MIN_COHORT_SIZE,
        "shown": [str(c) for c in shown],
        "partial_offsets": {str(c): int((last - c).n) for c in rate.index},
        "cohorts": [{"cohort": str(c), "size": int(size[c]),
                     "retention": [None if pd.isna(v) else float(v) for v in rate.loc[c]]}
                    for c in rate.index],
    }


# --- Products ---------------------------------------------------------------
def product_view(prior, current):
    """Compare revenue per product, with its category's direction.

    Args:
        prior (pandas.DataFrame): Order lines of the prior period.
        current (pandas.DataFrame): Order lines of the current period.

    Returns:
        pandas.DataFrame: Output of :func:`northwind.compare` by product
        plus ``category``, ``discontinued`` and ``category_growing``.
    """
    table = nw.compare(prior, current, "ProductName")
    info = pd.concat([prior, current]).groupby("ProductName").agg(
        category=("CategoryName", "first"), discontinued=("Discontinued", "first"))
    table = table.join(info)
    category_change = nw.compare(prior, current, "CategoryName").change
    table["category_growing"] = table.category.map(category_change > 0)
    return table


def product_summary(products):
    """Count declining products and the revenue they lost.

    Args:
        products (pandas.DataFrame): Output of :func:`product_view`.

    Returns:
        dict: ``products``, ``declining``,
        ``declining_in_growing_categories`` and
        ``revenue_lost_in_declining`` (US$, negative).
    """
    declining = products[products.change < 0]
    return {
        "products": len(products),
        "declining": len(declining),
        "declining_in_growing_categories": int(declining.category_growing.sum()),
        "revenue_lost_in_declining": float(declining.change.sum()),
    }


# --- Markets ----------------------------------------------------------------
def market_decline(prior, current):
    """Split each declining market's change into two effects.

    change = (N1 - N0) × S0 + N1 × (S1 - S0), where N is active
    customers and S is revenue per active customer.

    Args:
        prior (pandas.DataFrame): Order lines of the prior period.
        current (pandas.DataFrame): Order lines of the current period.

    Returns:
        pandas.DataFrame: Declining markets with ``customer_effect``
        and ``spend_effect``, largest drop first.

    Raises:
        AssertionError: If a declining market's two effects do not sum
            to its change.
    """
    table = nw.compare(prior, current, "Country")
    table["customers_prior"] = prior.groupby("Country").CustomerID.nunique()
    table["customers"] = current.groupby("Country").CustomerID.nunique()
    table = table.fillna({"customers_prior": 0, "customers": 0})
    spend_prior = table.prior / table.customers_prior
    spend = table.current / table.customers
    table["customer_effect"] = (table.customers - table.customers_prior) * spend_prior
    table["spend_effect"] = table.customers * (spend - spend_prior)
    declining = table[table.change < 0].sort_values("change")
    assert ((declining.customer_effect + declining.spend_effect - declining.change).abs() < 0.01).all()
    return declining


def largest_movers_in(declining_markets, customer_table, lines):
    """List the customers behind each declining market's change.

    Args:
        declining_markets (Iterable[str]): Market names.
        customer_table (pandas.DataFrame): Per-customer table from
            :func:`customer_bridge`.
        lines (pandas.DataFrame): All order lines, for names and
            countries.

    Returns:
        dict[str, list[dict]]: For each market, its customers'
        ``customer``, ``prior``, ``current``, ``change`` and
        ``segment``, largest drop first.
    """
    country = lines.groupby("CustomerID").Country.first()
    name = lines.groupby("CustomerID").CompanyName.first()
    out = {}
    for market in declining_markets:
        rows = customer_table[customer_table.index.map(country) == market].sort_values("change")
        out[market] = [{"customer": name[cid], "prior": r.prior, "current": r.current,
                        "change": r.change, "segment": r.segment} for cid, r in rows.iterrows()]
    return out


def narrate(result, bridge, declining_markets, overdue):
    """Write chart titles, legends, sources and the Q3 conclusions.

    Args:
        result (dict): Q3 result built in :func:`main`.
        bridge (pandas.DataFrame): Per-segment table from
            :func:`customer_bridge`.
        declining_markets (pandas.DataFrame): Declining markets from
            :func:`market_decline`.
        overdue (pandas.DataFrame): Overdue customers, highest trailing
            revenue first.

    Returns:
        dict: Text keyed by chart (``bridge``, ``products``,
        ``markets``, ``cohort``, ``rhythm``), plus ``finding`` and
        ``implication``.
    """
    r, ps, rh = result["retained"], result["product_summary"], result["rhythm"]
    windows = f"{nw.PRIOR_LABEL} vs {nw.CURRENT_LABEL}"
    spend_share = declining_markets.spend_effect.sum() / declining_markets.change.sum()
    names = list(declining_markets.index)
    drivers = [result["declining_market_customers"][m][0]["customer"] for m in names]
    top_overdue = list(overdue.customer.head(2))
    cohort = result["cohort_retention"]
    scored = rh["status_counts"].get("On rhythm", 0) + rh["overdue_customers"]
    return {
        "bridge": {
            "title": f"Existing customers added {nw.usd_k(bridge.change['Expansion'])}; "
                     f"{int(bridge.customers['Contraction'])} contracting accounts gave back "
                     f"{nw.usd_k(abs(bridge.change['Contraction']))}",
            "sub": nw.legend(f"Change in net revenue by customer group, in US$ thousands, {windows}",
                              "Dark blue: total revenue in each period",
                              "Blue: increase (new and expanding customers)",
                              "Orange: decrease (contracting and lost customers)",
                              "Number in brackets: customers in the group"),
            "src": f"Waterfall chart. Data: Orders, Order Details. n = {int(bridge.customers.sum())} customers",
        },
        "products": {
            "title": f"{ps['declining']} of {ps['products']} products declined, all inside growing categories, "
                     f"losing {nw.usd_k(abs(ps['revenue_lost_in_declining']))} combined",
            "sub": nw.legend(f"Change in net revenue by product, in US$ thousands, {windows}",
                              "Shown: the eight largest gains and every decline",
                              "Blue: products that grew",
                              "Orange: products that declined"),
            "src": f"Diverging bar chart. Data: Order Details, Product. n = {ps['products']} products",
        },
        "markets": {
            "title": f"{len(names)} markets declined; lower spend per customer explains "
                     f"{nw.pct(spend_share)} of the drop",
            "sub": nw.legend(f"Change in net revenue of each declining market, in US$ thousands, {windows}",
                              "Blue: effect of the change in the number of active customers",
                              "Orange: effect of the change in spend per customer",
                              "Grey text: the customer behind most of the decline"),
            "src": f"Stacked bar chart. Data: Orders, Order Details, Customers. n = {len(names)} declining markets",
        },
        "cohort": {
            "title": f"In a typical later quarter, {nw.pct(cohort['typical_retention'])} of a customer cohort "
                     "orders again",
            "sub": nw.legend("Share of each customer cohort that ordered again in each later quarter",
                              "Cohort: customers grouped by the quarter of their first order in the data",
                              "Darker blue: higher share",
                              "Asterisk (*): quarter with orders to 6 May 1998 only",
                              f"Cohorts with fewer than {cohort['min_cohort_size']} customers are left out"),
            "src": f"Cohort heatmap. Data: Orders. Cohorts of {cohort['min_cohort_size']} or more customers",
        },
        "rhythm": {
            "title": f"{rh['overdue_customers']} customers are overdue against their own order rhythm, with "
                     f"{nw.usd_k(rh['revenue_at_risk'])} of trailing revenue at stake",
            "sub": nw.legend(f"Each dot is one customer with {MIN_ORDERS_FOR_RHYTHM} or more orders",
                              "Across: usual days between orders (median)",
                              "Up: days since the last order, at 6 May 1998",
                              "Dot size: revenue in the last 12 months",
                              "Blue dot: ordering on rhythm",
                              f"Orange dot: overdue, more than {OVERDUE_MULTIPLE}× the usual gap",
                              f"Dashed orange line: {OVERDUE_MULTIPLE}× the usual gap",
                              "Dotted grey line: 1× the usual gap"),
            "src": f"Scatter and table. Data: Orders, Order Details. n = {scored} customers",
        },
        "finding": (
            f"Northwind keeps its customers: {r['retained_customers']} of {r['prior_customers']} bought again, and "
            f"the {int(bridge.customers['Lost'])} that left were worth {nw.usd_k(abs(bridge.change['Lost']))}. "
            f"The exposure sits inside retained accounts. {r['contracting_customers']} of them "
            f"({nw.pct(r['share_of_retained_contracting'])}) spent less, giving back "
            f"{nw.usd_k(abs(bridge.change['Contraction']))} that expansion elsewhere conceals. "
            f"{rh['overdue_customers']} customers have gone more than twice their usual interval without ordering, "
            f"including {top_overdue[0]} and {top_overdue[1]}; they account for {nw.usd_k(rh['revenue_at_risk'])}, "
            f"or {nw.pct(rh['revenue_at_risk_share'], digits=1)} of the last 12 months' revenue. Product and market "
            f"declines are small: {ps['declining']} products lost {nw.usd_k(abs(ps['revenue_lost_in_declining']))}, "
            f"and {nw.join_names(names)} lost {nw.usd_k(abs(declining_markets.change.sum()))} combined, led in "
            f"each case by one account ({nw.join_names(drivers)})."
        ),
        "implication": (
            "Retention effort belongs with contracting and overdue accounts. The overdue list is a ready win-back "
            "agenda, and the largest contracting accounts warrant a direct conversation about what changed. "
            "Track net revenue retention and order rhythm monthly so that weakening relationships surface while "
            "they are still recoverable. The declining products and markets are small enough for routine review, "
            "starting with the single account behind each market's drop."
        ),
    }


def method():
    """List the definitions shown in the Q3 method card.

    Args:
        None.

    Returns:
        list[list[str]]: ``[term, definition]`` pairs.
    """
    return [
        ["Customer groups", "New: ordered in the later period but not the earlier one. Expansion: ordered in both "
         "periods and spent more. Contraction: ordered in both periods and spent less. Lost: ordered in the "
         "earlier period but not the later one."],
        ["Customer retention", "The share of the earlier period's customers who ordered again in the later period."],
        ["Market decline split", "Customer effect = change in active customers × earlier spend per customer. Spend "
         "effect = later active customers × change in spend per customer. The two add up to the market's change."],
        ["Usual gap", f"The median number of days between a customer's consecutive orders, for customers with "
         f"{MIN_ORDERS_FOR_RHYTHM} or more orders."],
        ["Overdue customer", f"Days since the last order, counted at 6 May 1998 (the last order date in the data), "
         f"exceed {OVERDUE_MULTIPLE}× the customer's usual gap. An order placed after the data ends would not "
         "appear."],
        ["Revenue at risk", "Overdue customers' net revenue in the 12 months before 6 May 1998."],
        ["Cohort retention", f"The share of a cohort (defined in 01) who ordered in each later quarter. Cohorts "
         f"under {MIN_COHORT_SIZE} customers are left out."],
        ["Square-root scale", "Spreads out values near zero while keeping the 1× and 2× reference lines straight."],
    ]


def add_notes(text, result, bridge, declining_markets, overdue):
    """Add a description and a takeaway to each Q3 chart.

    Args:
        text (dict): Output of :func:`narrate`; updated in place.
        result (dict): Q3 result built in :func:`main`.
        bridge (pandas.DataFrame): Per-segment table from
            :func:`customer_bridge`.
        declining_markets (pandas.DataFrame): Declining markets from
            :func:`market_decline`.
        overdue (pandas.DataFrame): Overdue customers, highest trailing
            revenue first.

    Returns:
        None. Adds ``about`` and ``takeaway`` entries to ``text``.
    """
    seg, n = bridge.change, bridge.customers
    total = seg.sum()
    text["bridge"]["about"] = "The revenue change split by customer group, as a waterfall."
    text["bridge"]["takeaway"] = (
        f"Existing customers buying more ({int(n['Expansion'])}) added {nw.usd_k(seg['Expansion'])}, and "
        f"{int(n['New'])} new customers added {nw.usd_k(seg['New'])}. Contraction among {int(n['Contraction'])} "
        f"customers cost {nw.usd_k(abs(seg['Contraction']))}, about {abs(seg['Contraction'] / seg['Lost']):.0f}× "
        f"the {nw.usd_k(abs(seg['Lost']))} lost when {int(n['Lost'])} customers left. The main retention risk is "
        "customers who stay and spend less.")

    ps = result["product_summary"]
    movers = result["product_movers"]
    gain = movers[0]
    worst = min(movers, key=lambda r: r["change"])
    where = (f"and all {ps['declining']} sit in categories that grew overall"
             if ps["declining_in_growing_categories"] == ps["declining"] else
             f"and {ps['declining_in_growing_categories']} sit in categories that grew overall")
    text["products"]["about"] = "The products with the largest gains, and every product that declined."
    text["products"]["takeaway"] = (
        f"Only {ps['declining']} of {ps['products']} products declined, losing "
        f"{nw.usd_k(abs(ps['revenue_lost_in_declining']))} combined, {where}. The largest decline was "
        f"{worst['product']} ({nw.usd_k(worst['change'], signed=True)}); the largest gain, {gain['product']}, added "
        f"{nw.usd_k(gain['change'])}. Product decline is a small risk next to customer contraction "
        f"({nw.usd_k(abs(seg['Contraction']))}).")

    names = list(declining_markets.index)
    lost_customers = declining_markets[declining_markets.customers < declining_markets.customers_prior].index
    drop = abs(declining_markets.change.sum())
    spend_share = declining_markets.spend_effect.sum() / declining_markets.change.sum()
    who = (f"only {nw.join_names(lost_customers)} lost active customers" if len(lost_customers)
           else "none of them lost active customers")
    text["markets"]["about"] = ("Each declining market's change, split into the effect of fewer customers and the "
                                "effect of lower spend per customer.")
    text["markets"]["takeaway"] = (
        f"{nw.join_names(names)} lost {nw.usd_k(drop)} combined, {nw.pct(drop / total, digits=1)} of the total "
        f"increase. Lower spend per customer explains {nw.pct(spend_share)} of it, and {who}. In each market a "
        "single account drives the drop.")

    rh = result["rhythm"]
    top2 = overdue.head(2)
    late = overdue.sort_values("overdue_ratio", ascending=False).iloc[0]
    text["rhythm"]["about"] = ("Each customer's time since the last order against their own usual gap. Dots above "
                               "the dashed line are overdue.")
    text["rhythm"]["takeaway"] = (
        f"{rh['overdue_customers']} customers are overdue, holding {nw.usd_k(rh['revenue_at_risk'])} "
        f"({nw.pct(rh['revenue_at_risk_share'], digits=1)}) of the last 12 months' revenue. "
        f"{nw.join_names(top2.customer)} account for {nw.usd_k(top2.trailing_12m_revenue.sum())} of it. "
        f"{late.customer} is the most overdue: its last order was {int(late.days_since_last)} days ago, against a "
        f"usual gap of {late.median_gap:g} days.")

    c = result["cohort_retention"]
    shown = [r for r in c["cohorts"] if r["cohort"] in c["shown"]]
    early = [v for r in shown for v in r["retention"][1:3] if v is not None]
    later = [v for o, r in ((o, r) for r in shown for o in range(3, len(r["retention"])))
             if (v := r["retention"][o]) is not None and o != c["partial_offsets"][r["cohort"]]]
    steady = sum(later) / len(later) >= sum(early) / len(early) - 0.02
    first = shown[0]
    last_full = c["partial_offsets"][first["cohort"]] - 1
    text["cohort"]["about"] = "Retention by cohort: the share of each group of customers ordering again in each later quarter."
    text["cohort"]["takeaway"] = (
        f"In a typical later quarter {nw.pct(c['typical_retention'])} of a cohort orders again, "
        f"{'with no decline in later quarters' if steady else 'with a decline in later quarters'}: "
        f"{nw.pct(first['retention'][last_full])} of the {first['cohort'].replace('Q', ' Q')} cohort ordered "
        f"{last_full} quarters after joining. This steady retention is what lets the early cohorts in Figure 1.4 "
        "keep growing.")


def main():
    """Run the Q3 analysis.

    Args:
        None.

    Returns:
        None. Writes ``docs/data/q3.json`` and prints a summary.
    """
    lines, orders = nw.load()
    prior, current = nw.both_windows(lines)
    names = lines.groupby("CustomerID").CompanyName.first()
    countries = lines.groupby("CustomerID").Country.first()

    # Customers
    customer_table, bridge = customer_bridge(prior, current)
    customer_table["customer"] = names
    customer_table["market"] = countries
    rhythm = order_rhythm(orders, names)
    rhythm["market"] = countries
    rhythm["trailing_12m_revenue"] = trailing_revenue(lines).reindex(rhythm.index).fillna(0.0)
    rhythm["last_order"] = rhythm.last_order.dt.strftime("%Y-%m-%d")
    overdue = rhythm[rhythm.status == "Overdue"].sort_values("trailing_12m_revenue", ascending=False)
    trailing_total = float(rhythm.trailing_12m_revenue.sum())

    # Products
    products = product_view(prior, current)
    product_stats = product_summary(products)
    movers = pd.concat([products.head(8), products[products.change < 0]])

    # Markets
    declining_markets = market_decline(prior, current)

    result = {
        "windows": {"prior": nw.PRIOR_LABEL, "current": nw.CURRENT_LABEL},
        "retained": retained_customer_metrics(customer_table),
        "rhythm": {
            "status_counts": rhythm.status.value_counts().to_dict(),
            "overdue_customers": len(overdue),
            "revenue_at_risk": float(overdue.trailing_12m_revenue.sum()),
            "revenue_at_risk_share": float(overdue.trailing_12m_revenue.sum() / trailing_total),
            "customers": nw.records(rhythm.set_index("customer")[
                ["market", "orders", "median_gap", "days_since_last", "overdue_ratio", "status",
                 "trailing_12m_revenue", "last_order"]], "customer"),
            "overdue": nw.records(overdue.set_index("customer")[
                ["market", "orders", "median_gap", "days_since_last", "overdue_ratio",
                 "trailing_12m_revenue", "last_order"]], "customer"),
        },
        "cohort_retention": cohort_retention(orders),
        "product_summary": product_stats,
        "product_movers": nw.records(movers[["category", "prior", "current", "change", "growth"]], "product"),
        "declining_markets": nw.records(declining_markets[
            ["prior", "current", "change", "growth", "customers_prior", "customers",
             "customer_effect", "spend_effect"]], "market"),
        "declining_market_customers": largest_movers_in(declining_markets.index, customer_table, lines),
    }
    seg = bridge.change
    result["waterfall"] = nw.waterfall(
        nw.PRIOR_LABEL, prior.Revenue.sum(),
        [(f"New customers ({int(bridge.customers['New'])})", seg["New"]),
         (f"Expansion ({int(bridge.customers['Expansion'])})", seg["Expansion"]),
         (f"Contraction ({int(bridge.customers['Contraction'])})", seg["Contraction"]),
         (f"Lost customers ({int(bridge.customers['Lost'])})", seg["Lost"])],
        nw.CURRENT_LABEL)
    result["text"] = narrate(result, bridge, declining_markets, overdue)
    add_notes(result["text"], result, bridge, declining_markets, overdue)
    result["text"]["method"] = method()
    nw.save("q3", result)

    pd.set_option("display.width", 220)
    print("\nQ3 customer bridge\n", bridge.round(0).to_string())
    print("retained:", {k: round(v, 3) for k, v in result["retained"].items()})
    print("rhythm:", result["rhythm"]["status_counts"], "| at risk $%.0f (%.1f%% of trailing 12m)"
          % (result["rhythm"]["revenue_at_risk"], result["rhythm"]["revenue_at_risk_share"] * 100))
    print(overdue[["customer", "market", "orders", "median_gap", "days_since_last", "overdue_ratio",
                   "trailing_12m_revenue"]].round(1).to_string())
    print("\nproducts:", {k: round(v, 3) for k, v in product_stats.items()})
    print(movers[["category", "prior", "current", "change"]].round(0).to_string())
    print("\ndeclining markets\n", declining_markets.round(2).to_string())
    for market, rows in result["declining_market_customers"].items():
        print(market, [(r["customer"][:22], round(r["change"]), r["segment"]) for r in rows])
    print("\ncohort retention")
    for c in result["cohort_retention"]["cohorts"]:
        print(" ", c["cohort"], c["size"], [None if v is None else round(v, 2) for v in c["retention"]])


if __name__ == "__main__":
    main()
