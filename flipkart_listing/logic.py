# logic.py

SIZES = [
    "1 - 2 Years", "2 - 3 Years", "3 - 4 Years", "4 - 5 Years",
    "5 - 6 Years", "6 - 7 Years", "7 - 8 Years", "8 - 9 Years",
    "9 - 10 Years", "10 - 11 Years", "11 - 12 Years",
    "12 - 13 Years", "13 - 14 Years", "14 - 15 Years"
]

LABEL_SIZE_MAP = {
    "1 - 2 Years": "1 - 2 Years",
    "2 - 3 Years": "3 - 4 Years",
    "3 - 4 Years": "3 - 4 Years",
    "4 - 5 Years": "5 - 6 Years",
    "5 - 6 Years": "5 - 6 Years",
    "6 - 7 Years": "7 - 8 Years",
    "7 - 8 Years": "7 - 8 Years",
    "8 - 9 Years": "9 - 10 Years",
    "9 - 10 Years": "9 - 10 Years",
    "10 - 11 Years": "11 - 12 Years",
    "11 - 12 Years": "11 - 12 Years",
    "12 - 13 Years": "14 - 15 Years",
    "13 - 14 Years": "14 - 15 Years",
    "14 - 15 Years": "14 - 15 Years"
}

def size_to_code(size: str) -> str:
    # "1 - 2 Years" → "1_2"
    return size.replace(" Years", "").replace(" ", "").replace("-", "_")

def generate_rows(base_sku: str, base_data: dict, prices: list):
    if len(prices) != len(SIZES):
        raise ValueError("Exactly 14 prices are required")

    rows = []

    for i, size in enumerate(SIZES):
        row = base_data.copy()

        row["Size"] = size
        row["Label Size"] = LABEL_SIZE_MAP[size]
        row["Your selling price (INR)"] = prices[i]
        row["Group ID"] = base_sku
        row["Style Code"] = base_sku
        row["Seller SKU ID"] = f"{base_sku}_{size_to_code(size)}"

        rows.append(row)

    return rows
