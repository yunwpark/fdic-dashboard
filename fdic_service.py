"""Retrieve and aggregate FDIC 2025:Q4 institution financials.

The FDIC API returns JSON so the program can verify the reported total and
paginate safely. After retrieval, all financial work uses pandas DataFrames.
FDIC monetary fields are reported in thousands of U.S. dollars.
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass

import pandas as pd
import requests


API_URL = "https://api.fdic.gov/banks/financials"
REPORT_DATE = "20251231"
PAGE_SIZE = 10_000

FIELDS = [
    "CERT", "NAME", "REPDTE", "ASSET", "CHBAL", "SC", "FED",
    "LNLSNET", "TRADE", "ORE", "INTAN", "LIAB", "DEP", "DEPDOM",
    "DEPFOR", "FREPO", "OTHBOR", "SUBND", "EQTOT",
]

FINANCIAL_FIELDS = [
    field for field in FIELDS if field not in {"CERT", "NAME", "REPDTE"}
]
REQUIRED_TOTAL_FIELDS = ["ASSET", "LIAB"]
COMPONENT_FIELDS = [
    field for field in FINANCIAL_FIELDS if field not in REQUIRED_TOTAL_FIELDS
]


@dataclass
class FDICResult:
    institutions: pd.DataFrame
    balance_sheet: pd.DataFrame
    institution_count: int
    difference_usd_thousands: float


def fetch_all_financials(report_date: str = REPORT_DATE) -> pd.DataFrame:
    """Download every FDIC record for one report date and return a DataFrame."""
    rows: list[dict] = []
    offset = 0
    expected_total: int | None = None

    with requests.Session() as session:
        session.headers.update({"User-Agent": "FDIC-Flask-Dashboard/1.0"})

        while expected_total is None or offset < expected_total:
            params = {
                "filters": f"REPDTE:{report_date}",
                "fields": ",".join(FIELDS),
                "format": "json",
                "limit": PAGE_SIZE,
                "offset": offset,
                "sort_by": "CERT",
                "sort_order": "ASC",
            }

            for attempt in range(5):
                try:
                    response = session.get(API_URL, params=params, timeout=120)
                    response.raise_for_status()
                    payload = response.json()
                    break
                except (requests.RequestException, ValueError):
                    if attempt == 4:
                        raise
                    time.sleep(2**attempt)

            expected_total = int(payload["meta"]["total"])
            page = [item["data"] for item in payload.get("data", [])]
            if not page:
                break
            rows.extend(page)
            offset += len(page)

    if expected_total is None or len(rows) != expected_total:
        raise RuntimeError(
            f"FDIC reported {expected_total} records, but {len(rows)} were downloaded."
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError(f"No FDIC records were found for {report_date}.")

    missing_columns = [field for field in FIELDS if field not in df.columns]
    if missing_columns:
        raise RuntimeError(f"FDIC response omitted fields: {missing_columns}")

    for field in FINANCIAL_FIELDS:
        df[field] = pd.to_numeric(df[field], errors="raise")

    if df[REQUIRED_TOTAL_FIELDS].isna().any().any():
        raise RuntimeError(
            "The FDIC response contains missing assets or liabilities."
        )

    # A small number of foreign-bank branches report no separate EQTOT and
    # report assets equal to liabilities. In that exact case, book equity is
    # economically zero and can be made explicit without changing the identity.
    missing_equity = df["EQTOT"].isna()
    if missing_equity.any():
        implied_equity = df.loc[missing_equity, "ASSET"] - df.loc[missing_equity, "LIAB"]
        if (implied_equity.abs() > 1).any():
            raise RuntimeError(
                "Missing equity cannot be inferred from assets and liabilities."
            )
        df.loc[missing_equity, "EQTOT"] = implied_equity

    # FDIC component accounts may be blank when an institution reports no
    # amount for that category. Core accounting totals are never filled.
    df[COMPONENT_FIELDS] = df[COMPONENT_FIELDS].fillna(0.0)

    if df["CERT"].duplicated().any():
        raise RuntimeError("Duplicate FDIC certificate numbers were downloaded.")

    return df.sort_values("CERT").reset_index(drop=True)


def build_balance_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate institution rows into a mutually exclusive balance sheet."""
    df = df.copy()
    asset_components = ["CHBAL", "SC", "FED", "LNLSNET", "TRADE", "ORE", "INTAN"]
    liability_components = ["DEP", "FREPO", "OTHBOR", "SUBND"]

    df["OTHER_ASSETS_CALC"] = df["ASSET"] - df[asset_components].sum(axis=1)
    df["OTHER_LIABILITIES_CALC"] = (
        df["LIAB"] - df[liability_components].sum(axis=1)
    )

    columns_to_sum = [
        "ASSET", *asset_components, "OTHER_ASSETS_CALC",
        "LIAB", *liability_components, "OTHER_LIABILITIES_CALC",
        "EQTOT", "DEPDOM", "DEPFOR",
    ]
    totals = df[columns_to_sum].sum()

    lines = [
        ("Assets", "Total assets", totals["ASSET"], "total"),
        ("Assets", "Cash and balances due", totals["CHBAL"], "component"),
        ("Assets", "Securities", totals["SC"], "component"),
        ("Assets", "Federal funds sold and reverse repos", totals["FED"], "component"),
        ("Assets", "Net loans and leases", totals["LNLSNET"], "component"),
        ("Assets", "Trading assets", totals["TRADE"], "component"),
        ("Assets", "Other real estate owned", totals["ORE"], "component"),
        ("Assets", "Goodwill and other intangible assets", totals["INTAN"], "component"),
        ("Assets", "Other assets (calculated residual)", totals["OTHER_ASSETS_CALC"], "component"),
        ("Liabilities and equity", "Total liabilities", totals["LIAB"], "total"),
        ("Liabilities and equity", "Deposits", totals["DEP"], "component"),
        ("Deposit detail", "Domestic-office deposits", totals["DEPDOM"], "detail"),
        ("Deposit detail", "Foreign-office deposits", totals["DEPFOR"], "detail"),
        ("Liabilities and equity", "Federal funds purchased and repos", totals["FREPO"], "component"),
        ("Liabilities and equity", "Other borrowed funds", totals["OTHBOR"], "component"),
        ("Liabilities and equity", "Subordinated debt", totals["SUBND"], "component"),
        ("Liabilities and equity", "Other liabilities (calculated residual)", totals["OTHER_LIABILITIES_CALC"], "component"),
        ("Liabilities and equity", "Total equity capital", totals["EQTOT"], "total"),
        ("Liabilities and equity", "Total liabilities and equity", totals["LIAB"] + totals["EQTOT"], "total"),
    ]

    balance_sheet = pd.DataFrame(
        lines,
        columns=["section", "account", "amount_usd_thousands", "row_type"],
    )
    balance_sheet["amount_usd_billions"] = (
        balance_sheet["amount_usd_thousands"] / 1_000_000
    )
    balance_sheet["share_of_total_assets_pct"] = (
        balance_sheet["amount_usd_thousands"] / totals["ASSET"] * 100
    )
    return balance_sheet


def validate(df: pd.DataFrame, balance_sheet: pd.DataFrame) -> float:
    """Validate each institution and the aggregate accounting identity."""
    institution_differences = df["ASSET"] - df["LIAB"] - df["EQTOT"]
    if (institution_differences.abs() > 1).any():
        bad = int((institution_differences.abs() > 1).sum())
        raise RuntimeError(f"Accounting identity failed for {bad} institutions.")

    assets = float(df["ASSET"].sum())
    liabilities_plus_equity = float(df["LIAB"].sum() + df["EQTOT"].sum())
    difference = assets - liabilities_plus_equity
    if abs(difference) > 1:
        raise RuntimeError(
            f"Aggregate assets differ from liabilities plus equity by "
            f"${difference:,.0f} thousand."
        )

    reported_total = balance_sheet.loc[
        balance_sheet["account"] == "Total liabilities and equity",
        "amount_usd_thousands",
    ].iloc[0]
    if abs(float(reported_total) - assets) > 1:
        raise RuntimeError("The displayed balance sheet failed validation.")
    return difference


def load_fdic_result() -> FDICResult:
    institutions = fetch_all_financials()
    balance_sheet = build_balance_sheet(institutions)
    difference = validate(institutions, balance_sheet)
    return FDICResult(
        institutions=institutions,
        balance_sheet=balance_sheet,
        institution_count=len(institutions),
        difference_usd_thousands=difference,
    )


def dataframe_to_csv_bytes(df: pd.DataFrame) -> io.BytesIO:
    buffer = io.BytesIO()
    buffer.write(df.to_csv(index=False).encode("utf-8-sig"))
    buffer.seek(0)
    return buffer

