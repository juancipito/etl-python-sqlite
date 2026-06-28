from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parent
RAW_PATH = ROOT / "raw_data.csv"
CLEAN_PATH = ROOT / "clean_data.csv"
REJECTED_PATH = ROOT / "rejected_data.csv"
DB_PATH = ROOT / "synthetic_operations.db"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CATEGORY_MAP = {
    "software": "Software",
    "soft ware": "Software",
    "hardware": "Hardware",
    "hard-ware": "Hardware",
    "training": "Training",
    "train": "Training",
    "support": "Support",
    "customer support": "Support",
}
STATUS_MAP = {
    "complete": "Completed",
    "completed": "Completed",
    "done": "Completed",
    "pending": "Pending",
    "open": "Pending",
    "cancelled": "Cancelled",
    "canceled": "Cancelled",
}


def normalize_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def transform(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = raw.copy()
    frame.columns = [column.strip().lower() for column in frame.columns]
    frame["source_row"] = range(2, len(frame) + 2)

    for column in ["transaction_id", "customer_name", "email", "category", "status", "region"]:
        frame[column] = normalize_text(frame[column])

    frame["email"] = frame["email"].str.lower()
    frame["category_normalized"] = frame["category"].str.lower().map(CATEGORY_MAP)
    frame["status_normalized"] = frame["status"].str.lower().map(STATUS_MAP)
    frame["region"] = frame["region"].fillna("Unknown").replace("", "Unknown").str.title()
    frame["transaction_date_parsed"] = pd.to_datetime(frame["transaction_date"], errors="coerce")
    frame["updated_at_parsed"] = pd.to_datetime(frame["updated_at"], errors="coerce")
    frame["amount_numeric"] = pd.to_numeric(frame["amount"], errors="coerce")

    frame = frame.sort_values(["transaction_id", "updated_at_parsed"], na_position="first")
    frame["duplicate_id"] = frame.duplicated("transaction_id", keep="last")

    def issues(row: pd.Series) -> list[str]:
        found = []
        if pd.isna(row["transaction_id"]) or not str(row["transaction_id"]).strip():
            found.append("missing_transaction_id")
        if pd.isna(row["customer_name"]) or not str(row["customer_name"]).strip():
            found.append("missing_customer_name")
        if pd.isna(row["transaction_date_parsed"]):
            found.append("invalid_transaction_date")
        if pd.isna(row["amount_numeric"]) or row["amount_numeric"] <= 0:
            found.append("invalid_amount")
        if pd.isna(row["email"]) or not EMAIL_RE.match(str(row["email"])):
            found.append("invalid_email")
        if pd.isna(row["category_normalized"]):
            found.append("unknown_category")
        if pd.isna(row["status_normalized"]):
            found.append("unknown_status")
        if row["duplicate_id"]:
            found.append("superseded_duplicate")
        return found

    frame["quality_issues"] = frame.apply(lambda row: "|".join(issues(row)), axis=1)
    frame["quality_issue_count"] = frame["quality_issues"].str.count(r"\|") + frame["quality_issues"].ne("").astype(int)

    valid = frame["quality_issues"].eq("")
    clean = frame.loc[valid, [
        "transaction_id",
        "transaction_date_parsed",
        "customer_name",
        "email",
        "category_normalized",
        "amount_numeric",
        "status_normalized",
        "region",
        "updated_at_parsed",
        "source_row",
    ]].copy()
    clean.columns = [
        "transaction_id",
        "transaction_date",
        "customer_name",
        "email",
        "category",
        "amount",
        "status",
        "region",
        "updated_at",
        "source_row",
    ]
    clean["amount"] = clean["amount"].round(2)
    clean = clean.sort_values(["transaction_date", "transaction_id"]).reset_index(drop=True)

    rejected = frame.loc[~valid, [
        "source_row",
        "transaction_id",
        "transaction_date",
        "customer_name",
        "email",
        "category",
        "amount",
        "status",
        "region",
        "updated_at",
        "quality_issues",
    ]].sort_values("source_row")

    summary = pd.DataFrame(
        [
            {"metric": "raw_rows", "value": len(raw)},
            {"metric": "clean_rows", "value": len(clean)},
            {"metric": "rejected_rows", "value": len(rejected)},
            {"metric": "duplicate_rows_rejected", "value": int(frame["duplicate_id"].sum())},
            {"metric": "clean_amount_total", "value": round(clean["amount"].sum(), 2)},
        ]
    )
    return clean, rejected, summary


def load_sqlite(clean: pd.DataFrame, rejected: pd.DataFrame, summary: pd.DataFrame) -> None:
    with sqlite3.connect(DB_PATH) as connection:
        clean.to_sql("clean_transactions", connection, if_exists="replace", index=False)
        rejected.to_sql("rejected_transactions", connection, if_exists="replace", index=False)
        summary.to_sql("quality_summary", connection, if_exists="replace", index=False)


def main() -> None:
    raw = pd.read_csv(RAW_PATH, dtype="string")
    clean, rejected, summary = transform(raw)
    clean.to_csv(CLEAN_PATH, index=False, date_format="%Y-%m-%d")
    rejected.to_csv(REJECTED_PATH, index=False)
    load_sqlite(clean, rejected, summary)
    print(summary.to_string(index=False))
    print(f"Saved {CLEAN_PATH.name}, {REJECTED_PATH.name}, and {DB_PATH.name}")


if __name__ == "__main__":
    main()
