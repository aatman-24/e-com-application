# logic/return_logic.py

import pandas as pd
import os
from datetime import datetime
from pathlib import Path

def generate_return_report(returns_file: str, mapping_file: str, output_dir: str) -> str:
    """
    Reads returns CSV and SKU mapping, processes the data,
    and exports an Excel report. Returns the output file path.
    """

    # Convert to absolute paths (important!)
    returns_file = os.path.abspath(returns_file)
    mapping_file = os.path.abspath(mapping_file)
    output_dir = os.path.abspath(output_dir)

    # Load CSVs (skip first 8 rows for returns)
    df = pd.read_csv(returns_file, skiprows=7)
    mapping = pd.read_csv(mapping_file)

    # Clean columns
    df.columns = df.columns.str.strip()
    df["SKU"] = df["SKU"].astype(str).str.strip()
    df["Variation"] = df["Variation"].astype(str).str.strip()
    mapping["Parent_SKU"] = mapping["Parent_SKU"].astype(str).str.strip()
    mapping["Child_SKU"] = mapping["Child_SKU"].astype(str).str.strip()

    # Merge mapping
    df = df.merge(mapping, left_on="SKU", right_on="Child_SKU", how="left")
    df["Parent_SKU"] = df["Parent_SKU"].fillna(df["SKU"])

    # Custom size order
    size_order = [
        "6-12 Months", "0-1 Years", "1-2 Years", "2-3 Years", "3-4 Years",
        "4-5 Years", "5-6 Years", "6-7 Years", "7-8 Years", "8-9 Years",
        "9-10 Years", "10-11 Years", "11-12 Years", "12-13 Years",
        "13-14 Years", "14-15 Years"
    ]
    df["Variation"] = pd.Categorical(df["Variation"], categories=size_order, ordered=True)

    # Group by Parent SKU + Size
    sku_size_summary = (
        df.groupby(["Parent_SKU", "Variation"], observed=True)["Qty"]
        .sum()
        .reset_index()
        .sort_values(["Parent_SKU", "Variation"])
    )

    # Add blank rows between groups
    grouped_rows = []
    for parent, group in sku_size_summary.groupby("Parent_SKU"):
        grouped_rows.append(group)
        grouped_rows.append(pd.DataFrame([["", "", ""]], columns=sku_size_summary.columns))
    spaced = pd.concat(grouped_rows, ignore_index=True)

    # Create grouped summary
    grouped = (
        sku_size_summary.groupby("Parent_SKU")
        .apply(lambda x: dict(zip(x["Variation"], x["Qty"])))
        .reset_index()
    )
    grouped.columns = ["Parent_SKU", "Size_Wise_Returns"]

    # Save Excel
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%d-%m-%Y")
    output_file = Path(output_dir) / f"{date_str}_meesho_return_analysis.xlsx"

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        spaced.to_excel(writer, sheet_name="Parent+Size Detailed", index=False)
        grouped.to_excel(writer, sheet_name="Grouped Report", index=False)

    return str(output_file)
