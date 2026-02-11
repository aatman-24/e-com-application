# #!/usr/bin/env python3
# """
# SKU-wise Profit & Return Analysis
# FINAL – Order-Level Accurate Version

# ✔ Order-month cohort based
# ✔ Multi-size, multi-price safe
# ✔ Customer-return aware
# ✔ No averaging
# ✔ Finance-grade accuracy
# """

# import pandas as pd

# # -----------------------
# # CONFIG
# # -----------------------
# ORDER_FILE = "order_data.csv"      # November orders
# RETURN_FILE = "return_data.csv"    # Last 6 months returns
# OUTPUT_FILE = "sku_profit_report.csv"

# BUYING_PRICE = 200
# REVERSE_SHIPPING = 163
# PER_UNIT_DEDUCTION = 10


# # -----------------------
# # LOAD DATA
# # -----------------------
# orders = pd.read_csv(ORDER_FILE)
# returns = pd.read_csv(RETURN_FILE, skiprows=7)


# # -----------------------
# # STEP 1: FILTER DELIVERED ORDERS (COHORT)
# # -----------------------
# orders = orders[
#     orders["Reason for Credit Entry"] == "DELIVERED"
# ].copy()

# orders["Quantity"] = orders["Quantity"].astype(int)
# orders["selling_price"] = orders[
#     "Supplier Discounted Price (Incl GST and Commision)"
# ].astype(float)

# orders = orders[[
#     "Sub Order No",
#     "SKU",
#     "Quantity",
#     "selling_price"
# ]]


# # -----------------------
# # STEP 2: FILTER CUSTOMER RETURNS
# # -----------------------
# returns = returns[
#     returns["Type of Return"] == "Customer Return"
# ].copy()

# returns["Qty"] = returns["Qty"].astype(int)

# returns = returns[[
#     "Suborder Number",
#     "Qty",
#     "Return Created Date"
# ]]

# # Safety: remove duplicate exports
# returns = returns.drop_duplicates(
#     subset=["Suborder Number", "Qty", "Return Created Date"]
# )


# # -----------------------
# # STEP 3: MATCH RETURNS TO ORDERS
# # -----------------------
# returns_matched = returns[
#     returns["Suborder Number"].isin(orders["Sub Order No"])
# ]

# # print(returns_matched)

# # Aggregate returns per order
# returns_per_order = (
#     returns_matched
#     .groupby("Suborder Number", as_index=False)
#     .agg(returned_qty=("Qty", "sum"))
# )
# # print("returns_per_order")
# # print(returns_per_order)

# # -----------------------
# # STEP 4: ORDER-LEVEL NETTING
# # -----------------------
# df = orders.merge(
#     returns_per_order,
#     left_on="Sub Order No",
#     right_on="Suborder Number",
#     how="left"
# )

# df["returned_qty"] = df["returned_qty"].fillna(0).astype(int)

# # Cap safety (never allow return > delivered)
# df["returned_qty"] = df[["Quantity", "returned_qty"]].min(axis=1)

# df["net_sold_qty"] = df["Quantity"] - df["returned_qty"]

# # -----------------------
# # STEP 5: ORDER-LEVEL PROFIT
# # -----------------------
# df["order_profit"] = (
#     # Revenue from sold units
#     (df["net_sold_qty"] * df["selling_price"])
#     # Buying cost (only sold units)
#     - (df["net_sold_qty"] * BUYING_PRICE)
#     # Reverse shipping (only returned units)
#     - (df["returned_qty"] > 0).astype(int) * REVERSE_SHIPPING
#     # Per-unit deduction (delivered units)
#     - (df["net_sold_qty"] * PER_UNIT_DEDUCTION)
# )


# # -----------------------
# # STEP 6: SKU-LEVEL AGGREGATION
# # -----------------------
# sku_report = (
#     df
#     .groupby("SKU", as_index=False)
#     .agg(
#         delivered_qty=("Quantity", "sum"),
#         returned_qty=("returned_qty", "sum"),
#         net_sold_qty=("net_sold_qty", "sum"),
#         net_revenue=("order_profit", "sum")
#     )
# )

# sku_report["customer_return_pct"] = (
#     (sku_report["returned_qty"] / sku_report["delivered_qty"]) * 100
# ).round(2)


# # -----------------------
# # OUTPUT
# # -----------------------
# sku_report = sku_report.sort_values("net_revenue")

# sku_report.to_csv(OUTPUT_FILE, index=False)

# print(f"✅ Final SKU profit report generated: {OUTPUT_FILE}")


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

# -----------------------
# CONFIG
# -----------------------
ORDER_FILE = "order_data.csv"
RETURN_FILE = "return_data.csv"
BUYING_PRICE_FILE = "sku_buying_price.csv"
OUTPUT_FILE = "sku_profit_report_3.csv"

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
