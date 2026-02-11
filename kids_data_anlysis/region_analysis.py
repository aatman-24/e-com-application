#!/usr/bin/env python3
"""
E-commerce Region Analysis
Extended Version:
- Delivered Orders
- RTO Orders (RTO_COMPLETE + CANCELLED)
- Cancelled Orders
- Exchanged Orders
"""

import pandas as pd
from pathlib import Path

# -----------------------
# CONFIG
# -----------------------
INPUT_DIR = "data"
OUTPUT_FILE = "state_wise_order_analysis.csv"

REQUIRED_COLUMNS = [
    "Reason for Credit Entry",
    "Order Date",
    "Customer State",
    "SKU",
    "Size"
]

# -----------------------
# LOAD & MERGE CSV FILES
# -----------------------
dfs = []
for file in Path(INPUT_DIR).glob("*.csv"):
    print(f"Loading: {file.name}")
    dfs.append(pd.read_csv(file))

merged_df = pd.concat(dfs, ignore_index=True)

df = merged_df[REQUIRED_COLUMNS].copy()

# -----------------------
# CLEANING
# -----------------------
df["Customer State"] = df["Customer State"].str.strip()
df["Reason for Credit Entry"] = df["Reason for Credit Entry"].str.strip()

# -----------------------
# BASE: TOTAL ORDERS
# -----------------------
total_orders = (
    df.groupby("Customer State")
      .size()
      .reset_index(name="Total Orders")
)

# -----------------------
# DELIVERED ORDERS
# -----------------------
delivered_orders = (
    df[df["Reason for Credit Entry"] == "DELIVERED"]
    .groupby("Customer State")
    .size()
    .reset_index(name="Delivered Orders")
)

# -----------------------
# RTO ORDERS (RTO + CANCELLED)
# -----------------------
rto_orders = (
    df[df["Reason for Credit Entry"].isin(["RTO_COMPLETE", "CANCELLED"])]
    .groupby("Customer State")
    .size()
    .reset_index(name="RTO Orders")
)

# -----------------------
# CANCELLED ONLY
# -----------------------
cancelled_orders = (
    df[df["Reason for Credit Entry"] == "CANCELLED"]
    .groupby("Customer State")
    .size()
    .reset_index(name="Cancelled Orders")
)

# -----------------------
# EXCHANGED ORDERS
# -----------------------
exchanged_orders = (
    df[df["Reason for Credit Entry"] == "DOOR_STEP_EXCHANGED"]
    .groupby("Customer State")
    .size()
    .reset_index(name="Exchanged Orders")
)

# -----------------------
# MERGE ALL RESULTS
# -----------------------
final_report = total_orders \
    .merge(delivered_orders, on="Customer State", how="left") \
    .merge(rto_orders, on="Customer State", how="left") \
    .merge(cancelled_orders, on="Customer State", how="left") \
    .merge(exchanged_orders, on="Customer State", how="left") \
    .fillna(0)

# Convert counts to int
count_cols = [
    "Delivered Orders",
    "RTO Orders",
    "Cancelled Orders",
    "Exchanged Orders"
]
final_report[count_cols] = final_report[count_cols].astype(int)

# -----------------------
# PERCENTAGE METRICS
# -----------------------
final_report["Delivered %"] = (
    final_report["Delivered Orders"] / final_report["Total Orders"] * 100
).round(2)

final_report["RTO %"] = (
    final_report["RTO Orders"] / final_report["Total Orders"] * 100
).round(2)

final_report["Cancelled %"] = (
    final_report["Cancelled Orders"] / final_report["Total Orders"] * 100
).round(2)

final_report["Exchanged %"] = (
    final_report["Exchanged Orders"] / final_report["Total Orders"] * 100
).round(2)

# -----------------------
# SORT & SAVE
# -----------------------
final_report = final_report.sort_values("Total Orders", ascending=False)

final_report.to_csv(OUTPUT_FILE, index=False)

print("\n✅ State-wise order analysis generated successfully")
print(final_report.head(30))
