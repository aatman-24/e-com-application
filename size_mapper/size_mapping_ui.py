#!/usr/bin/env python3

import tkinter as tk
from tkinter import scrolledtext

# === Original size mapping and logic ===
size_mapping = {
    "6-12": "1-2", "0-1": "1-2", "1-2": "1-2",
    "2-3": "3-4", "3-4": "3-4",
    "4-5": "5-6", "5-6": "5-6",
    "6-7": "7-8", "7-8": "7-8",
    "8-9": "9-10", "9-10": "9-10",
    "10-11": "11-12", "11-12": "11-12",
    "12-13": "13-14", "13-14": "13-14", "14-15": "13-14"
}

customer_size_order = [
    "0-1", "6-12", "1-2", "2-3", "3-4", "4-5", "5-6",
    "6-7", "7-8", "8-9", "9-10", "10-11", "11-12", "12-13", "13-14", "14-15"
]

production_size_order = [
    "1-2", "3-4", "5-6", "7-8", "9-10", "11-12", "13-14"
]

# === Processing Logic ===
def process_input(input_text: str) -> str:
    customer_orders = []
    for line in input_text.strip().splitlines():
        size = line.strip()
        if size:
            customer_orders.append(size)

    customer_count = {}
    for size in customer_orders:
        customer_count[size] = customer_count.get(size, 0) + 1

    production_count = {}
    for size, count in customer_count.items():
        production_size = size_mapping.get(size, size)
        production_count[production_size] = production_count.get(production_size, 0) + count

    total_pieces = sum(production_count.values())

    output_lines = []

    output_lines.append("\nProduction Size Orders:")
    for size in production_size_order:
        if size in production_count:
            output_lines.append(f"{size}({production_count[size]})")

    output_lines.append("\n---")
    output_lines.append(f"TOTAL PIECES: {total_pieces}")

    return "\n".join(output_lines)

# === GUI ===
root = tk.Tk()
root.title("Size Mapping Tool")
root.geometry("900x650")

tk.Label(root, text="Enter customer sizes (one per line):", font=("Arial", 12, "bold")).pack(pady=5)
input_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=100, height=18, font=("Consolas", 10))
input_box.pack(padx=10, pady=5)

tk.Label(root, text="Output:", font=("Arial", 12, "bold")).pack(pady=5)
output_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=100, height=12, font=("Consolas", 10))
output_box.pack(padx=10, pady=5)

# === Button Actions ===
def on_submit():
    input_text = input_box.get("1.0", tk.END)
    output_text = process_input(input_text)
    output_box.delete("1.0", tk.END)
    output_box.insert(tk.END, output_text)

def on_clear():
    input_box.delete("1.0", tk.END)
    output_box.delete("1.0", tk.END)

# === Keyboard Shortcuts ===
def select_all(event):
    event.widget.tag_add("sel", "1.0", "end")
    return "break"

def copy(event):
    event.widget.event_generate("<<Copy>>")
    return "break"

def cut(event):
    event.widget.event_generate("<<Cut>>")
    return "break"

# Bind shortcuts for both input & output
for widget in [input_box, output_box]:
    widget.bind("<Control-a>", select_all)
    widget.bind("<Control-A>", select_all)
    widget.bind("<Control-c>", copy)
    widget.bind("<Control-C>", copy)
    widget.bind("<Control-x>", cut)
    widget.bind("<Control-X>", cut)

# === Buttons ===
btn_frame = tk.Frame(root)
btn_frame.pack(pady=10)

submit_btn = tk.Button(btn_frame, text="Submit", command=on_submit,
                       font=("Arial", 12), bg="#4CAF50", fg="white", width=12)
submit_btn.pack(side=tk.LEFT, padx=10)

clear_btn = tk.Button(btn_frame, text="Clear", command=on_clear,
                      font=("Arial", 12), bg="#f44336", fg="white", width=12)
clear_btn.pack(side=tk.LEFT, padx=10)

root.mainloop()
