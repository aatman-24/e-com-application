#!/usr/bin/env python3

import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
from datetime import datetime
from pathlib import Path
import subprocess
import os

# === CONFIG ===

# Get the directory where this script is located
BASE_DIR = Path(__file__).resolve().parent

mapping_file = BASE_DIR / "data" / "sku_mapping.csv"
output_dir = Path("output")
output_dir.mkdir(parents=True, exist_ok=True)

# === CORE LOGIC ===
def generate_report(returns_file):
    try:
        skiprows = 7

        df = pd.read_csv(returns_file, skiprows=skiprows)
        mapping = pd.read_csv(mapping_file)

        # Clean Columns
        df.columns = df.columns.str.strip()
        df["SKU"] = df["SKU"].astype(str).str.strip()
        df["Variation"] = df["Variation"].astype(str).str.strip()
        mapping["Parent_SKU"] = mapping["Parent_SKU"].astype(str).str.strip()
        mapping["Child_SKU"] = mapping["Child_SKU"].astype(str).str.strip()

        # Merge Mapping
        df = df.merge(mapping, left_on="SKU", right_on="Child_SKU", how="left")
        df["Parent_SKU"] = df["Parent_SKU"].fillna(df["SKU"])

        # Size Mapping
        size_mapping = {
            "0-6 Months": "1-2 Years",
            "6-12 Months": "1-2 Years",
            "0-1 Years": "1-2 Years",
            "1-2 Years": "1-2 Years",
            "2-3 Years": "3-4 Years",
            "3-4 Years": "3-4 Years",
            "4-5 Years": "5-6 Years",
            "5-6 Years": "5-6 Years",
            "6-7 Years": "7-8 Years",
            "7-8 Years": "7-8 Years",
            "8-9 Years": "9-10 Years",
            "9-10 Years": "9-10 Years",
            "10-11 Years": "11-12 Years",
            "11-12 Years": "11-12 Years",
            "12-13 Years": "13-14 Years",
            "13-14 Years": "13-14 Years",
            "14-15 Years": "13-14 Years"
        }

        production_size_order = [
            "1-2 Years", "3-4 Years", "5-6 Years", "7-8 Years",
            "9-10 Years", "11-12 Years", "13-14 Years"
        ]
        prod_order_index = {s: i for i, s in enumerate(production_size_order)}

        df["Production_Size"] = df["Variation"].map(size_mapping).fillna(df["Variation"])
        df["Production_Size_sort_idx"] = df["Production_Size"].map(prod_order_index).fillna(len(prod_order_index)).astype(int)

        production_summary = (
            df.groupby(["Parent_SKU", "Production_Size", "Production_Size_sort_idx"], observed=True)["Qty"]
            .sum()
            .reset_index()
            .sort_values(["Parent_SKU", "Production_Size_sort_idx"])
            .drop(columns="Production_Size_sort_idx")
        )

        grouped_rows = []
        for parent, group in production_summary.groupby("Parent_SKU", sort=False):
            grouped_rows.append(group)
            grouped_rows.append(pd.DataFrame([["", "", ""]], columns=production_summary.columns))

        production_summary_spaced = pd.concat(grouped_rows, ignore_index=True)

        # Output
        now = datetime.now()
        date_str = now.strftime("%d-%m-%Y")
        time_str = now.strftime("%H_%M")  # e.g. 05_02 or 18_30
        output_file = output_dir / f"{date_str}_{time_str}_production_size_report.xlsx"

        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            production_summary_spaced.to_excel(writer, sheet_name="Parent+Production Detailed", index=False)

        return str(output_file)

    except Exception as e:
        raise RuntimeError(str(e))


# === UI LOGIC ===
def browse_file():
    default_dir = str(Path.home() / "Downloads")
    file_path = filedialog.askopenfilename(
        title="Select Returns CSV File",
        filetypes=[("CSV files", "*.csv")],
        initialdir=default_dir
    )
    if file_path:
        entry_returns_file.delete(0, tk.END)
        entry_returns_file.insert(0, file_path)


def open_output_folder():
    try:
        subprocess.run(["xdg-open", str(output_dir)], check=False)
    except Exception:
        messagebox.showerror("Error", f"❌ Could not open folder:\n{output_dir}")


def run_report():
    returns_file = entry_returns_file.get().strip()
    if not returns_file:
        messagebox.showwarning("Missing File", "Please select a returns CSV file first.")
        return

    try:
        output_path = generate_report(returns_file)
        messagebox.showinfo("Success", f"✅ Report generated successfully:\n{output_path}")
    except Exception as e:
        messagebox.showerror("Error", f"❌ Failed to generate report:\n{e}")


# === UI SETUP ===
root = tk.Tk()
root.title("Daily Return Count")
root.geometry("700x280")
root.resizable(False, False)
root.configure(bg="#f4f4f9")

tk.Label(root, text="Daily Return Count", font=("Helvetica", 16, "bold"), bg="#f4f4f9").pack(pady=10)

frame = tk.Frame(root, bg="#f4f4f9")
frame.pack(pady=10)

tk.Label(frame, text="Select Returns CSV File:", bg="#f4f4f9").grid(row=0, column=0, padx=5, pady=5, sticky="w")
entry_returns_file = tk.Entry(frame, width=55)
entry_returns_file.grid(row=0, column=1, padx=5, pady=5)
tk.Button(frame, text="Browse", command=browse_file, bg="#0078D7", fg="white", relief="raised").grid(row=0, column=2, padx=5, pady=5)

# Buttons Frame
button_frame = tk.Frame(root, bg="#f4f4f9")
button_frame.pack(pady=15)

tk.Button(button_frame, text="Generate Report", command=run_report, bg="#28a745", fg="white", width=20, height=2).grid(row=0, column=0, padx=10)
tk.Button(button_frame, text="Open Output Folder", command=open_output_folder, bg="#6c757d", fg="white", width=20, height=2).grid(row=0, column=1, padx=10)

tk.Label(root, text=f"Using fixed mapping file: {mapping_file}", bg="#f4f4f9", fg="gray", font=("Helvetica", 9)).pack(pady=5)

root.mainloop()
