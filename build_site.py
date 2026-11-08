"""Fetch FDIC data and build the static GitHub Pages dashboard."""
from datetime import datetime, timezone
from pathlib import Path
from shutil import copytree

from jinja2 import Environment, FileSystemLoader, select_autoescape

from fdic_service import dataframe_to_csv_bytes, load_fdic_result

ROOT = Path(__file__).resolve().parent
templates = Environment(
    loader=FileSystemLoader(ROOT / "templates"),
    autoescape=select_autoescape(["html"]),
)

def account_value(balance_sheet, account: str) -> float:
    return float(
        balance_sheet.loc[
            balance_sheet["account"] == account, "amount_usd_billions"
        ].iloc[0]
    )


def render_dashboard(result, loaded_at):
    bs = result.balance_sheet
    records = bs.to_dict(orient="records")

    asset_accounts = [
        "Cash and balances due", "Securities", "Net loans and leases",
        "Trading assets", "Goodwill and other intangible assets",
        "Other assets (calculated residual)",
    ]
    asset_chart = {
        "labels": asset_accounts,
        "values": [account_value(bs, account) for account in asset_accounts],
    }
    funding_chart = {
        "labels": ["Deposits", "Other liabilities", "Equity capital"],
        "values": [
            account_value(bs, "Deposits"),
            account_value(bs, "Total liabilities") - account_value(bs, "Deposits"),
            account_value(bs, "Total equity capital"),
        ],
    }

    return templates.get_template("index.html").render(
        rows=records,
        institution_count=result.institution_count,
        total_assets=account_value(bs, "Total assets"),
        total_liabilities=account_value(bs, "Total liabilities"),
        total_equity=account_value(bs, "Total equity capital"),
        deposits=account_value(bs, "Deposits"),
        difference=result.difference_usd_thousands,
        loaded_at=loaded_at,
        asset_chart=asset_chart,
        funding_chart=funding_chart,
    )


def build_site(result, output):
    loaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page = render_dashboard(result, loaded_at)
    copytree(ROOT / "static", output / "static", dirs_exist_ok=True)
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / "fdic_2025q4_aggregate_balance_sheet.csv").write_bytes(
        dataframe_to_csv_bytes(result.balance_sheet).getvalue()
    )
    (output / "fdic_2025q4_institution_financials.csv").write_bytes(
        dataframe_to_csv_bytes(result.institutions).getvalue()
    )


if __name__ == "__main__":
    build_site(load_fdic_result(), ROOT / "_site")
