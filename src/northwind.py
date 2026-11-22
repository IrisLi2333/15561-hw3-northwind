"""Shared data loading, comparison periods and text helpers.

Every analysis script imports this module, so net revenue, the
comparison periods and the market definition are defined once.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "raw" / "northwind.xlsx"
OUT_DIR = ROOT / "docs" / "data"

# Year-over-year comparison: the longest pair of periods covering the same
# months of the year (the data holds 22 complete months, Jul 1996 - Apr 1998).
PRIOR = (pd.Timestamp("1996-07-01"), pd.Timestamp("1997-05-01"))
CURRENT = (pd.Timestamp("1997-07-01"), pd.Timestamp("1998-05-01"))
PRIOR_LABEL = "Jul 1996–Apr 1997"
CURRENT_LABEL = "Jul 1997–Apr 1998"
TREND_END = pd.Timestamp("1998-05-01")       # monthly trends stop at April 1998
DATA_END = pd.Timestamp("1998-05-06")        # last order date in the data
TOTAL_NET_REVENUE = 1_265_793.04             # reconciliation target, all periods


def load():
    """Load the workbook and build the order-line table.

    Args:
        None.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: ``lines``, one row
        per order line with net revenue and customer, product, category
        and employee attributes; and ``orders``, the raw Orders sheet.

    Raises:
        AssertionError: If the joins change the number of order lines
            or net revenue does not reconcile to ``TOTAL_NET_REVENUE``.
    """
    sheets = pd.read_excel(DATA_FILE, sheet_name=None)
    orders = sheets["Orders"]
    details = sheets["Orders Details"].copy()
    customers = sheets["Customers"][["CustomerID", "CompanyName", "Country"]]
    products = sheets["Product"][["ProductID", "ProductName", "CategoryID", "Discontinued"]]
    categories = sheets["Categories"][["CategoryID", "CategoryName"]]
    employees = sheets["Employees"][["EmployeeID", "FirstName", "LastName", "Title", "Country"]].rename(
        columns={"Country": "EmployeeCountry"})

    # Net revenue from the price actually charged on each line. Discounts carry
    # float noise (0.0499999...), so they are rounded to two decimals first.
    details["Revenue"] = details.UnitPrice * details.Quantity * (1 - details.Discount.round(2))

    lines = (details
             .merge(orders[["OrderID", "CustomerID", "EmployeeID", "OrderDate"]], on="OrderID", validate="m:1")
             .merge(customers, on="CustomerID", validate="m:1")
             .merge(products, on="ProductID", validate="m:1")
             .merge(categories, on="CategoryID", validate="m:1")
             .merge(employees, on="EmployeeID", validate="m:1"))
    lines["Month"] = lines.OrderDate.dt.to_period("M")

    assert len(lines) == len(details), "joins must not duplicate or drop order lines"
    assert abs(lines.Revenue.sum() - TOTAL_NET_REVENUE) < 0.01, "revenue must reconcile"
    return lines, orders


def in_window(df, window):
    """Select rows whose order date falls in a half-open window.

    Args:
        df (pandas.DataFrame): Rows with an ``OrderDate`` column.
        window (tuple[pandas.Timestamp, pandas.Timestamp]): Start
            (inclusive) and end (exclusive).

    Returns:
        pandas.DataFrame: The rows inside ``[start, end)``.
    """
    start, end = window
    return df[(df.OrderDate >= start) & (df.OrderDate < end)]


def both_windows(lines):
    """Split order lines into the two comparison periods.

    Args:
        lines (pandas.DataFrame): Order lines from :func:`load`.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: Lines in ``PRIOR``
        and lines in ``CURRENT``.
    """
    return in_window(lines, PRIOR), in_window(lines, CURRENT)


def pct_change(new, old):
    """Return the relative change from ``old`` to ``new``.

    Args:
        new (float): Value in the later period.
        old (float): Value in the earlier period.

    Returns:
        float | None: ``new / old - 1``, or None when ``old`` is zero.
    """
    return None if old == 0 else new / old - 1


def compare(prior, current, key):
    """Compare net revenue per group across the two periods.

    Args:
        prior (pandas.DataFrame): Order lines of the prior period.
        current (pandas.DataFrame): Order lines of the current period.
        key (str): Column to group by, e.g. ``"Country"``.

    Returns:
        pandas.DataFrame: One row per group with ``prior``, ``current``,
        ``change`` (US$) and ``growth`` (ratio, None for new groups),
        sorted by ``change``, largest first. A group missing from one
        period counts as zero revenue there.
    """
    table = pd.DataFrame({
        "prior": prior.groupby(key).Revenue.sum(),
        "current": current.groupby(key).Revenue.sum(),
    }).fillna(0.0)
    table["change"] = table.current - table.prior
    table["growth"] = [pct_change(c, p) for c, p in zip(table.current, table.prior)]
    return table.sort_values("change", ascending=False)


def records(table, index_name):
    """Convert a DataFrame to JSON-ready records.

    Args:
        table (pandas.DataFrame): Table to convert.
        index_name (str): Field name given to the index.

    Returns:
        list[dict]: One dict per row, index included.
    """
    return json.loads(table.reset_index(names=index_name).to_json(orient="records"))


def _clean(value):
    """Make a value JSON-serialisable.

    Recurses into dicts, lists and tuples, turns NaN into None and numpy
    scalars into Python types, and rounds floats to 4 decimals.

    Args:
        value (Any): Value to clean.

    Returns:
        Any: The cleaned value; dict keys become strings.
    """
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    return round(value, 4) if isinstance(value, float) else value


def save(name, payload):
    """Write an analysis result to ``docs/data/<name>.json``.

    Args:
        name (str): File stem, e.g. ``"q1"``.
        payload (dict): Result to write; cleaned with :func:`_clean`.

    Returns:
        None. Writes the file and prints its path.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.json"
    path.write_text(json.dumps(_clean(payload), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def usd_k(value, signed=False):
    """Format a dollar amount for display text.

    Args:
        value (float): Amount in US dollars.
        signed (bool): Prefix ``+`` to positive amounts.

    Returns:
        str: ``'$757.9K'`` from 1,000 upward, ``'$248'`` below;
        negative amounts carry a minus sign.
    """
    sign = ("+" if value > 0 else "−" if value < 0 else "") if signed else ("−" if value < 0 else "")
    amount = abs(value)
    return f"{sign}${amount / 1000:,.1f}K" if amount >= 1000 else f"{sign}${amount:,.0f}"


def pct(value, signed=False, digits=0):
    """Format a ratio as a percentage.

    Args:
        value (float): Ratio, e.g. 0.898.
        signed (bool): Prefix ``+`` to non-negative values.
        digits (int): Decimal places.

    Returns:
        str: Percentage text, e.g. ``'90%'``; negative values carry a
        minus sign.
    """
    text = f"{abs(value) * 100:.{digits}f}%"
    if signed:
        return ("+" if value >= 0 else "−") + text
    return ("−" if value < 0 else "") + text


def join_names(names):
    """Join names into an English list.

    Args:
        names (Iterable): Items to join; each is converted to str.

    Returns:
        str: ``'A'``, ``'A and B'`` or ``'A, B and C'``.
    """
    names = [str(n) for n in names]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"


def waterfall(start_label, start, steps, end_label):
    """Build the bars of a waterfall chart.

    Args:
        start_label (str): Label of the starting total.
        start (float): Starting total in US$.
        steps (list[tuple[str, float]]): Label and signed change of each
            step.
        end_label (str): Label of the ending total.

    Returns:
        list[dict]: Bars with ``label``, ``value`` and ``kind``
        (``'total'``, ``'up'`` or ``'down'``); the last bar is the start
        plus every change.
    """
    out = [{"label": start_label, "value": start, "kind": "total"}]
    out += [{"label": label, "value": value, "kind": "up" if value >= 0 else "down"} for label, value in steps]
    out.append({"label": end_label, "value": start + sum(v for _, v in steps), "kind": "total"})
    return out


def legend(*items):
    """Join the lines of a chart subtitle.

    Args:
        *items (str): The measure line, then one legend item per line.

    Returns:
        str: The lines joined by newlines.
    """
    return "\n".join(items)


def month_name(period):
    """Spell out a month.

    Args:
        period (str): Month as ``'YYYY-MM'``.

    Returns:
        str: Month and year, e.g. ``'September 1996'``.
    """
    return pd.Period(period, freq="M").strftime("%B %Y")
