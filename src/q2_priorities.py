"""Q2 analysis: markets and categories a small team should prioritise.

Run ``python src/q2_priorities.py`` from the project root; it writes
``docs/data/q2.json``.
"""
import pandas as pd

import northwind as nw

GAP_INDEX = 0.5            # a category is a gap when its share in a market is under half its company share
ACCOUNT_LED_SHARE = 0.5    # a market is account-led when one customer brings half or more of its revenue


def portfolio(prior, current, key):
    """Measure scale, growth and reach for each market or category.

    Args:
        prior (pandas.DataFrame): Order lines of the prior period.
        current (pandas.DataFrame): Order lines of the current period.
        key (str): ``"Country"`` or ``"CategoryName"``.

    Returns:
        pandas.DataFrame: Output of :func:`northwind.compare` plus
        ``customers``, ``customers_prior``, ``orders``,
        ``revenue_per_customer``, ``aov`` and revenue ``share``.
    """
    table = nw.compare(prior, current, key)
    table["customers"] = current.groupby(key).CustomerID.nunique()
    table["customers_prior"] = prior.groupby(key).CustomerID.nunique()
    table["orders"] = current.groupby(key).OrderID.nunique()
    table = table.fillna({"customers": 0, "customers_prior": 0, "orders": 0})
    table["revenue_per_customer"] = table.current / table.customers.where(table.customers > 0)
    table["aov"] = table.current / table.orders.where(table.orders > 0)
    table["share"] = table.current / table.current.sum()
    return table


def add_quadrants(table):
    """Assign each row to a growth-share quadrant.

    Rows at or above the median of both current revenue and dollar
    change are Invest; larger but slower, Defend; smaller but faster,
    Develop; the rest, Deprioritize.

    Args:
        table (pandas.DataFrame): Output of :func:`portfolio`; modified
            in place.

    Returns:
        pandas.DataFrame: The same table with a ``quadrant`` column.
    """
    large = table.current >= table.current.median()
    growing = table.change >= table.change.median()
    table["quadrant"] = "Deprioritize"
    table.loc[large & growing, "quadrant"] = "Invest"
    table.loc[~large & growing, "quadrant"] = "Develop"
    table.loc[large & ~growing, "quadrant"] = "Defend"
    return table


def top_customer_share(current):
    """Compute the largest customer's share of each market's revenue.

    Args:
        current (pandas.DataFrame): Order lines of the current period.

    Returns:
        pandas.Series: Share from 0 to 1, indexed by country.
    """
    by_customer = current.groupby(["Country", "CustomerID"]).Revenue.sum()
    return by_customer.groupby("Country").max() / by_customer.groupby("Country").sum()


def category_depth(current):
    """Measure how many product categories customers buy.

    Args:
        current (pandas.DataFrame): Order lines of the current period.

    Returns:
        tuple[pandas.Series, float]: Mean distinct categories per
        customer by country, and the mean over all customers.
    """
    per_customer = current.groupby(["Country", "CustomerID"]).CategoryName.nunique()
    return per_customer.groupby("Country").mean(), float(per_customer.mean())


def add_score(table):
    """Score each market by the average percentile of four measures.

    The measures, equally weighted, are current revenue, dollar change,
    revenue per customer and category depth.

    Args:
        table (pandas.DataFrame): Market table with those columns;
            modified in place.

    Returns:
        pandas.DataFrame: The same table with ``score`` (0 to 100) and
        ``rank`` (1 is highest).
    """
    parts = ["current", "change", "revenue_per_customer", "category_depth"]
    table["score"] = table[parts].rank(pct=True).mean(axis=1) * 100
    table["rank"] = table.score.rank(ascending=False, method="min").astype(int)
    return table


def market_category_grid(current, markets, categories):
    """Tabulate revenue for every market and category pair.

    Args:
        current (pandas.DataFrame): Order lines of the current period.
        markets (list[str]): Row order.
        categories (list[str]): Column order.

    Returns:
        pandas.DataFrame: Revenue with markets as rows and categories as
        columns; missing pairs are zero.
    """
    grid = current.pivot_table(index="Country", columns="CategoryName", values="Revenue",
                               aggfunc="sum", fill_value=0.0)
    return grid.reindex(index=markets, columns=categories, fill_value=0.0)


def cross_sell_gaps(grid, priority_markets):
    """Find under-represented categories in priority markets.

    A category is a gap when its share of the market's revenue, divided
    by its share of company revenue, is below ``GAP_INDEX``.

    Args:
        grid (pandas.DataFrame): Output of :func:`market_category_grid`.
        priority_markets (list[str]): Markets to check.

    Returns:
        list[dict]: Gaps with ``market``, ``category``, ``revenue``,
        ``index`` and ``opportunity`` (revenue needed to reach the
        company-wide share), largest opportunity first.
    """
    company_share = grid.sum(axis=0) / grid.values.sum()
    gaps = []
    for market in priority_markets:
        market_total = grid.loc[market].sum()
        for category, revenue in grid.loc[market].items():
            index = (revenue / market_total) / company_share[category]
            if index < GAP_INDEX:
                gaps.append({"market": market, "category": category, "revenue": revenue,
                             "index": index,
                             "opportunity": company_share[category] * market_total - revenue})
    return sorted(gaps, key=lambda g: -g["opportunity"])


def team_workload(prior, current):
    """Summarise the work each employee handled in both periods.

    Args:
        prior (pandas.DataFrame): Order lines of the prior period.
        current (pandas.DataFrame): Order lines of the current period.

    Returns:
        pandas.DataFrame: One row per employee with current-period
        orders, with ``title``, ``based_in``, ``orders``, ``revenue``,
        ``customers`` and ``countries``, the same four with a
        ``_prior`` suffix, ``name`` and ``orders_growth``; highest
        revenue first.
    """
    def per_employee(window_lines):
        """Aggregate one period's order lines by employee.

        Args:
            window_lines (pandas.DataFrame): Order lines of one period.

        Returns:
            pandas.DataFrame: ``orders``, ``revenue``, ``customers`` and
            ``countries`` per employee ID.
        """
        return window_lines.groupby("EmployeeID").agg(
            orders=("OrderID", "nunique"), revenue=("Revenue", "sum"),
            customers=("CustomerID", "nunique"), countries=("Country", "nunique"))

    a, b = per_employee(prior), per_employee(current)
    who = current.groupby("EmployeeID").agg(
        first=("FirstName", "first"), last=("LastName", "first"),
        title=("Title", "first"), based_in=("EmployeeCountry", "first"))
    table = who.join(b).join(a.add_suffix("_prior"))
    table["name"] = table["first"] + " " + table["last"]
    table["orders_growth"] = table.orders / table.orders_prior - 1
    return table.drop(columns=["first", "last"]).sort_values("revenue", ascending=False)


def team_summary(current, workload):
    """Summarise team-level workload and market coverage.

    Args:
        current (pandas.DataFrame): Order lines of the current period.
        workload (pandas.DataFrame): Output of :func:`team_workload`.

    Returns:
        dict: ``employees``, ``based_in``, ``markets_served``, average
        ``orders``, ``customers`` and ``countries`` per employee in
        both periods, and ``revenue_share_outside_home_countries``.
    """
    def avg(column):
        """Return the mean of a workload column.

        Args:
            column (str): Column of ``workload``.

        Returns:
            float: Mean across employees.
        """
        return float(workload[column].mean())

    employee_countries = set(current.EmployeeCountry.unique())
    home = current.Country.isin(employee_countries)
    return {
        "employees": len(workload),
        "based_in": sorted(employee_countries),
        "markets_served": int(current.Country.nunique()),
        "avg_orders": {"prior": avg("orders_prior"), "current": avg("orders")},
        "avg_customers": {"prior": avg("customers_prior"), "current": avg("customers")},
        "avg_countries": {"prior": avg("countries_prior"), "current": avg("countries")},
        "revenue_share_outside_home_countries": float(current[~home].Revenue.sum() / current.Revenue.sum()),
    }


def narrate(result, markets, categories, quadrant_summary):
    """Write chart titles, legends, sources and the Q2 conclusions.

    Args:
        result (dict): Q2 result built in :func:`main`.
        markets (pandas.DataFrame): Market table with quadrants, scores
            and ``account_led``.
        categories (pandas.DataFrame): Category table with quadrants.
        quadrant_summary (pandas.DataFrame): Markets, revenue and change
            per quadrant.

    Returns:
        dict: Text keyed by chart (``markets``, ``categories``,
        ``team``, ``grid``), plus ``finding`` and ``implication``.
    """
    invest = quadrant_summary.loc["Invest"]
    priority = markets[markets.quadrant == "Invest"]
    broad = priority[~priority.account_led].sort_values("current", ascending=False)
    led = priority[priority.account_led].sort_values("current", ascending=False)
    low = markets[markets.quadrant == "Deprioritize"]
    team, gaps = result["team_summary"], result["cross_sell_gaps"]
    top_dollar, fastest = categories.change.idxmax(), categories.growth.idxmax()
    lead_broad = broad.head(3)
    return {
        "markets": {
            "title": f"{int(invest.markets)} of {len(markets)} markets hold {nw.pct(invest.revenue_share)} of "
                     f"revenue and brought {nw.pct(invest.share_of_increase)} of the increase",
            "sub": nw.legend("Each bubble is one market (customer country)",
                              f"Across: net revenue in {nw.CURRENT_LABEL}, in US$ thousands (log scale)",
                              f"Up: change in net revenue vs {nw.PRIOR_LABEL}, in US$ thousands",
                              "Bubble size: number of active customers",
                              "Blue bubble: no single customer brings half of the market's revenue",
                              "Orange bubble: one customer brings half or more of the market's revenue",
                              "Dashed lines: medians, which divide the four quadrants"),
            "src": f"Bubble scatter. Data: Orders, Order Details, Customers. n = {len(markets)} markets",
        },
        "categories": {
            "title": f"{top_dollar} added the most dollars; {fastest} grew fastest "
                     f"({nw.pct(categories.growth[fastest], signed=True)})",
            "sub": nw.legend("Net revenue by product category, in US$ thousands",
                              f"Light blue dot: {nw.PRIOR_LABEL}",
                              f"Blue dot: {nw.CURRENT_LABEL}",
                              "Percentage: growth between the two periods"),
            "src": f"Dumbbell chart. Data: Order Details, Product, Categories. n = {len(categories)} categories",
        },
        "team": {
            "title": f"Each employee handled {team['avg_orders']['current']:.0f} orders on average, up from "
                     f"{team['avg_orders']['prior']:.0f}, across {team['avg_countries']['current']:.0f} countries",
            "sub": nw.legend(f"Work handled by each employee, {nw.PRIOR_LABEL} → {nw.CURRENT_LABEL}",
                              "Orders: orders the employee handled",
                              "Customers: distinct customers on those orders",
                              "Countries: countries those customers are in",
                              f"Revenue: net revenue of the orders handled in {nw.CURRENT_LABEL}"),
            "src": f"Table. Data: Orders, Employees, Customers. n = {team['employees']} employees",
        },
        "grid": {
            "title": f"{len(gaps)} category gaps in priority markets are worth about "
                     f"{nw.usd_k(result['cross_sell_opportunity_total'])} at the company-average mix",
            "sub": nw.legend(f"Net revenue by market and category in {nw.CURRENT_LABEL}, in US$ thousands",
                              "Darker blue: more revenue",
                              "Bold market name: priority market (Invest quadrant)",
                              "Orange outline: in a priority market, the category earns under half its "
                              "company-wide share of revenue",
                              "Dash: no sales"),
            "src": f"Heatmap. Data: Orders, Order Details, Customers, Product, Categories. "
                   f"n = {len(markets)} markets × {len(categories)} categories",
        },
        "finding": (
            f"{int(invest.markets)} of {len(markets)} markets combine above-median scale with above-median dollar "
            f"growth; together they hold {nw.pct(invest.revenue_share)} of revenue and brought "
            f"{nw.pct(invest.share_of_increase)} of the increase. {nw.join_names(lead_broad.index)} pair that "
            f"scale with a broad base of {nw.join_names(int(c) for c in lead_broad.customers)} customers. "
            f"{nw.join_names(led.index)} also rank highly, yet in each a single customer brings half or more of "
            f"the market's revenue. Among categories, {top_dollar} added the most dollars and {fastest} grew "
            f"fastest. The team is based in the {nw.join_names(team['based_in']).replace(' and ', ' and the ')}, while "
            f"{nw.pct(team['revenue_share_outside_home_countries'])} of revenue comes from other countries and "
            f"each employee serves customers in {team['avg_countries']['current']:.0f} countries on average."
        ),
        "implication": (
            f"Direct proactive sales effort to {nw.join_names(lead_broad.index)}, where scale, dollar growth and "
            f"customer breadth coincide. Manage {nw.join_names(led.index)} as key accounts, since their results "
            f"depend on one relationship each. Use the {len(gaps)} category gaps as the cross-selling agenda for "
            f"priority markets. Serve the {len(low)} lowest-priority markets through standard order handling, and "
            "assign each priority market a named owner so that attention follows the portfolio."
        ),
    }


def method():
    """List the definitions shown in the Q2 method card.

    Args:
        None.

    Returns:
        list[list[str]]: ``[term, definition]`` pairs.
    """
    return [
        ["Portfolio quadrants", "Markets and categories are split at the median of current revenue and the median "
         "of dollar change. Invest: both at or above the median. Develop: smaller, but growing at or above the "
         "median. Defend: larger, but growing below the median. Deprioritize: both below."],
        ["Priority market", "A market in the Invest quadrant."],
        ["Account-led market", f"One customer brings {nw.pct(ACCOUNT_LED_SHARE)} or more of the market's revenue."],
        ["Priority score", "The average percentile rank of a market's revenue, dollar change, revenue per customer "
         "and categories bought per customer, on a 0 to 100 scale. Shown when you hover over a bubble."],
        ["Category gap", f"In a priority market, a category whose share of the market's revenue is under "
         f"{nw.pct(GAP_INDEX)} of its share of company revenue. Its opportunity, an estimate assuming the company-wide "
         "mix, is the extra revenue needed to reach that share."],
        ["Log scale", "Each step along the axis multiplies revenue by the same factor, so small and large markets "
         "fit on one chart."],
        ["Countries per employee", "Distinct customer countries on the orders an employee handled."],
        ["Small markets", "Several markets have one or two active customers, so their percentages move with a "
         "single account."],
    ]


def add_notes(text, result, markets, categories, quadrant_summary, workload):
    """Add a description and a takeaway to each Q2 chart.

    Args:
        text (dict): Output of :func:`narrate`; updated in place.
        result (dict): Q2 result built in :func:`main`.
        markets (pandas.DataFrame): Market table with quadrants and
            ``account_led``.
        categories (pandas.DataFrame): Category table with quadrants.
        quadrant_summary (pandas.DataFrame): Markets, revenue and change
            per quadrant.
        workload (pandas.DataFrame): Output of :func:`team_workload`.

    Returns:
        None. Adds ``about`` and ``takeaway`` entries to ``text``.
    """
    invest = quadrant_summary.loc["Invest"]
    priority = markets[markets.quadrant == "Invest"]
    broad = priority[~priority.account_led].sort_values("current", ascending=False).head(3)
    led = priority[priority.account_led].sort_values("current", ascending=False)
    low = quadrant_summary.loc["Deprioritize"]
    text["markets"]["about"] = ("Each market placed by its size and its dollar growth. The dashed medians divide "
                                "the four quadrants.")
    text["markets"]["takeaway"] = (
        f"The {int(invest.markets)} Invest markets hold {nw.pct(invest.revenue_share)} of revenue and brought "
        f"{nw.pct(invest.share_of_increase)} of the increase. {nw.join_names(broad.index)} rest on "
        f"{nw.join_names(int(c) for c in broad.customers)} customers respectively, while "
        f"{nw.join_names(led.index)} each depend on one dominant account. The {int(low.markets)} Deprioritize "
        f"markets together bring {nw.pct(low.revenue_share)} of revenue.")

    largest = categories.sort_values("current", ascending=False).head(2)
    fastest, slowest = categories.growth.idxmax(), categories.growth.idxmin()
    text["categories"]["about"] = ("A dumbbell chart: each category's revenue in the earlier period and the later "
                                   "period, joined by a line.")
    text["categories"]["takeaway"] = (
        f"{nw.join_names(largest.index)} are the largest categories and added "
        f"{nw.usd_k(largest.change.sum())} combined. {fastest} grew fastest, from "
        f"{nw.usd_k(categories.prior[fastest])} to {nw.usd_k(categories.current[fastest])}. {slowest} grew "
        f"slowest, at {nw.pct(categories.growth[slowest], signed=True)}.")

    t = result["team_summary"]
    text["team"]["about"] = "Orders, customers and customer countries each employee handled in both periods."
    text["team"]["takeaway"] = (
        f"Orders per employee rose from {t['avg_orders']['prior']:.0f} to {t['avg_orders']['current']:.0f} on "
        f"average ({nw.pct(t['avg_orders']['current'] / t['avg_orders']['prior'] - 1, signed=True)}), and customer "
        f"countries per employee from {t['avg_countries']['prior']:.0f} to {t['avg_countries']['current']:.0f}. "
        f"Each employee served customers in {int(workload.countries.min())} to {int(workload.countries.max())} "
        f"countries. For a small team spread across all {t['markets_served']} markets, concentrating effort on the "
        "priority markets is the most direct lever.")

    gaps = result["cross_sell_gaps"]
    counts = pd.Series([g["market"] for g in gaps]).value_counts()
    most = counts.index[0]
    reason = (", consistent with a single customer buying a narrow range"
              if bool(markets.account_led[most]) else "")
    top = [f"{g['market']} {g['category']} ({nw.usd_k(g['opportunity'])})" for g in gaps[:3]]
    text["grid"]["about"] = ("Revenue for every market and category pair. Outlines mark where a priority market "
                             "buys far less of a category than the company average.")
    text["grid"]["takeaway"] = (
        f"The {len(gaps)} gaps add up to about {nw.usd_k(result['cross_sell_opportunity_total'])}. The largest are "
        f"{nw.join_names(top)}. {most} alone has {int(counts.iloc[0])} gaps{reason}.")


def main():
    """Run the Q2 analysis.

    Args:
        None.

    Returns:
        None. Writes ``docs/data/q2.json`` and prints a summary.
    """
    lines, _ = nw.load()
    prior, current = nw.both_windows(lines)

    markets = add_quadrants(portfolio(prior, current, "Country"))
    depth_by_market, depth_overall = category_depth(current)
    markets["category_depth"] = depth_by_market
    markets = add_score(markets)
    markets["top_customer_share"] = top_customer_share(current)
    markets["account_led"] = markets.top_customer_share >= ACCOUNT_LED_SHARE

    categories = add_quadrants(portfolio(prior, current, "CategoryName"))

    market_order = list(markets.sort_values("current", ascending=False).index)
    category_order = list(categories.sort_values("current", ascending=False).index)
    grid = market_category_grid(current, market_order, category_order)
    assert abs(grid.values.sum() - current.Revenue.sum()) < 0.01

    priority = list(markets[markets.quadrant == "Invest"].sort_values("score", ascending=False).index)
    gaps = cross_sell_gaps(grid, priority)

    workload = team_workload(prior, current)
    assert abs(workload.revenue.sum() - current.Revenue.sum()) < 0.01

    quadrant_summary = (markets.groupby("quadrant")
                        .agg(markets=("current", "size"), revenue=("current", "sum"), change=("change", "sum")))
    quadrant_summary["revenue_share"] = quadrant_summary.revenue / markets.current.sum()
    quadrant_summary["share_of_increase"] = quadrant_summary.change / markets.change.sum()

    result = {
        "windows": {"prior": nw.PRIOR_LABEL, "current": nw.CURRENT_LABEL},
        "markets": nw.records(markets.sort_values("score", ascending=False), "market"),
        "market_medians": {"current": float(markets.current.median()), "change": float(markets.change.median())},
        "quadrants": nw.records(quadrant_summary, "quadrant"),
        "priority_markets": priority,
        "categories": nw.records(categories, "category"),
        "category_medians": {"current": float(categories.current.median()),
                             "change": float(categories.change.median())},
        "category_depth_overall": depth_overall,
        "grid": {"markets": market_order, "categories": category_order,
                 "revenue": grid.values.round(2).tolist(),
                 "company_share": (grid.sum(axis=0) / grid.values.sum()).round(4).tolist()},
        "cross_sell_gaps": gaps,
        "cross_sell_opportunity_total": sum(g["opportunity"] for g in gaps),
        "team": nw.records(workload, "employee_id"),
        "team_summary": team_summary(current, workload),
    }
    result["text"] = narrate(result, markets, categories, quadrant_summary)
    add_notes(result["text"], result, markets, categories, quadrant_summary, workload)
    result["text"]["method"] = method()
    nw.save("q2", result)

    pd.set_option("display.width", 220)
    show = ["prior", "current", "change", "growth", "customers", "revenue_per_customer",
            "category_depth", "top_customer_share", "score", "quadrant"]
    print("\nQ2 markets\n", markets.sort_values("score", ascending=False)[show].round(2).to_string())
    print("\nquadrants\n", quadrant_summary.round(3).to_string())
    print("\ncategories\n", categories[["prior", "current", "change", "growth", "share", "customers", "quadrant"]]
          .round(2).to_string())
    print(f"\ncategory depth overall: {depth_overall:.2f} of 8")
    print("cross-sell gaps:", [(g["market"], g["category"], round(float(g["index"]), 2), round(g["opportunity"]))
                               for g in gaps])
    print("\nteam\n", workload[["name", "title", "based_in", "orders_prior", "orders", "customers_prior",
                               "customers", "countries_prior", "countries", "revenue"]].round(0).to_string())
    print(result["team_summary"])


if __name__ == "__main__":
    main()
