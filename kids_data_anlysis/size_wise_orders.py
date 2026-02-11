#!/usr/bin/env python3
"""
Size-wise Order Analysis
Goal: Identify which sizes get the most orders + percentage contribution
"""

import pandas as pd
from pathlib import Path

# -----------------------
# CONFIG
# -----------------------
INPUT_DIR = "data"
OUTPUT_FILE = "size_wise_order_analysis.csv"

# -----------------------
# LOAD & MERGE CSV FILES
# -----------------------
dfs = []
for file in Path(INPUT_DIR).glob("*.csv"):
    print(f"Loading: {file.name}")
    dfs.append(pd.read_csv(file))

if not dfs:
    raise Exception("No CSV files found!")

merged_df = pd.concat(dfs, ignore_index=True)

# -----------------------
# VALIDATE COLUMN
# -----------------------
if "Size" not in merged_df.columns:
    raise ValueError("Size column not found in input data")

df = merged_df[["Size"]].copy()

# -----------------------
# CLEAN SIZE DATA
# -----------------------
df["Size"] = (
    df["Size"]
    .astype(str)
    .str.strip()
    .str.replace("Years", "", regex=False)
    .str.replace("Year", "", regex=False)
)

df = df[df["Size"].notna() & (df["Size"] != "")]

# -----------------------
# SIZE-WISE ORDER COUNT
# -----------------------
size_orders = (
    df.groupby("Size")
      .size()
      .reset_index(name="Total Orders")
)

# -----------------------
# ADD PERCENTAGE
# -----------------------
total_orders = size_orders["Total Orders"].sum()

size_orders["Order %"] = (
    size_orders["Total Orders"] / total_orders * 100
).round(2)

# -----------------------
# SORT & SAVE
# -----------------------
size_orders = size_orders.sort_values("Total Orders", ascending=False)

size_orders.to_csv(OUTPUT_FILE, index=False)

print("\n✅ Size-wise order analysis with percentage generated successfully")
print(size_orders.head(15))
