
#!/usr/bin/env python3
"""
SKU-wise Profit & Return Analysis
FINAL – Order-Level Accurate Version (SKU Buying Price)

✔ Order-level profit
✔ Multi-size, multi-price safe
✔ SKU-wise buying price support
✔ Customer return aware
✔ Reverse shipping once per suborder
"""

import pandas as pd
from datetime import datetime


# -----------------------
# CONFIG
# -----------------------
import os
from pathlib import Path


ORDER_FILE = os.environ.get("ORDER_FILE", "order_data.csv")
RETURN_FILE = os.environ.get("RETURN_FILE", "return_data.csv")
BUYING_PRICE_FILE = os.environ.get("BUYING_PRICE_FILE", "sku_buying_price.csv")

timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")

downloads_dir = Path.home() / "Downloads"
downloads_dir.mkdir(exist_ok=True)

OUTPUT_FILE = downloads_dir / f"sku_profit_report_{timestamp}.csv"


REVERSE_SHIPPING = 163
PER_UNIT_DEDUCTION = 10


# -----------------------
# LOAD DATA
# -----------------------
orders = pd.read_csv(ORDER_FILE)
returns = pd.read_csv(RETURN_FILE, skiprows=7)
buying_prices = pd.read_csv(BUYING_PRICE_FILE)


# -----------------------
# VALIDATE BUYING PRICE FILE
# -----------------------
if "SKU" not in buying_prices.columns or "buying_price" not in buying_prices.columns:
    raise ValueError("Buying price file must contain columns: SKU,buying_price")

buying_prices["buying_price"] = buying_prices["buying_price"].astype(float)


# -----------------------
# STEP 1: FILTER DELIVERED ORDERS
# -----------------------
orders = orders[
    orders["Reason for Credit Entry"] == "DELIVERED"
].copy()

orders["Quantity"] = orders["Quantity"].astype(int)
orders["selling_price"] = orders[
    "Supplier Discounted Price (Incl GST and Commision)"
].astype(float)

orders = orders[[
    "Sub Order No",
    "SKU",
    "Quantity",
    "selling_price"
]]


# -----------------------
# STEP 2: ATTACH SKU BUYING PRICE
# -----------------------
orders = orders.merge(
    buying_prices,
    on="SKU",
    how="left"
)

# Fail fast if buying price missing
missing_bp = orders[orders["buying_price"].isna()]["SKU"].unique()
if len(missing_bp) > 0:
    raise ValueError(f"Missing buying price for SKUs: {missing_bp}")


# -----------------------
# STEP 3: FILTER CUSTOMER RETURNS
# -----------------------
returns = returns[
    returns["Type of Return"] == "Customer Return"
].copy()

returns["Qty"] = returns["Qty"].astype(int)

returns = returns[[
    "Suborder Number",
    "Qty",
    "Return Created Date"
]]

returns = returns.drop_duplicates(
    subset=["Suborder Number", "Qty", "Return Created Date"]
)


# -----------------------
# STEP 4: MATCH RETURNS TO ORDERS
# -----------------------
returns_matched = returns[
    returns["Suborder Number"].isin(orders["Sub Order No"])
]

returns_per_order = (
    returns_matched
    .groupby("Suborder Number", as_index=False)
    .agg(returned_qty=("Qty", "sum"))
)


# -----------------------
# STEP 5: ORDER-LEVEL NETTING
# -----------------------
df = orders.merge(
    returns_per_order,
    left_on="Sub Order No",
    right_on="Suborder Number",
    how="left"
)

df["returned_qty"] = df["returned_qty"].fillna(0).astype(int)
df["returned_qty"] = df[["Quantity", "returned_qty"]].min(axis=1)

df["net_sold_qty"] = df["Quantity"] - df["returned_qty"]


# -----------------------
# STEP 6: ORDER-LEVEL PROFIT
# -----------------------
df["order_profit"] = (
    # Revenue from sold units
    (df["net_sold_qty"] * df["selling_price"])
    # Buying cost (SKU-wise)
    - (df["net_sold_qty"] * df["buying_price"])
    # Reverse shipping (once per suborder if any return)
    - ((df["returned_qty"] > 0).astype(int) * REVERSE_SHIPPING)
    # Per-unit deduction (sold units only)
    - (df["net_sold_qty"] * PER_UNIT_DEDUCTION)
)


# -----------------------
# STEP 7: SKU-LEVEL AGGREGATION
# -----------------------
sku_report = (
    df
    .groupby("SKU", as_index=False)
    .agg(
        delivered_qty=("Quantity", "sum"),
        returned_qty=("returned_qty", "sum"),
        net_sold_qty=("net_sold_qty", "sum"),
        net_revenue=("order_profit", "sum")
    )
)

sku_report["customer_return_pct"] = (
    (sku_report["returned_qty"] / sku_report["delivered_qty"]) * 100
).round(2)


# -----------------------
# OUTPUT
# -----------------------
sku_report = sku_report.sort_values("net_revenue")

sku_report.to_csv(OUTPUT_FILE, index=False)

print(f"✅ Final SKU profit report generated: {OUTPUT_FILE}")
