# return_ui.py

import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import os
from pathlib import Path
from logic.return_logic import generate_return_report

class ReturnReportApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📦 Return Report Generator")
        self.root.geometry("600x400")

        self.returns_path = tk.StringVar()
        self.mapping_path = tk.StringVar()
        self.output_dir = os.path.join(os.getcwd(), "output")

        tk.Label(root, text="Return Data CSV:", font=("Arial", 11)).pack(pady=(20, 5))
        tk.Entry(root, textvariable=self.returns_path, width=60).pack()
        tk.Button(root, text="Browse", command=self.load_returns).pack(pady=5)

        tk.Label(root, text="SKU Mapping CSV:", font=("Arial", 11)).pack(pady=(20, 5))
        tk.Entry(root, textvariable=self.mapping_path, width=60).pack()
        tk.Button(root, text="Browse", command=self.load_mapping).pack(pady=5)

        tk.Button(root, text="Generate Report", bg="#4CAF50", fg="white",
                  font=("Arial", 12, "bold"), command=self.generate_report).pack(pady=20)

        tk.Button(root, text="Open Output Folder", bg="#2196F3", fg="white",
                  font=("Arial", 11), command=self.open_output_folder).pack(pady=10)

    def load_returns(self):
        default_dir = str(Path.home() / "Downloads")
        file = filedialog.askopenfilename(
            title="Select Returns CSV File",
            filetypes=[("CSV files", "*.csv")],
            initialdir=default_dir
        )
        if file:
            self.returns_path.set(file)

    def load_mapping(self):
        # file = filedialog.askopenfilename(title="Select SKU Mapping CSV", filetypes=[("CSV Files", "*.csv")])
        # Use a fixed mapping file path
        mapping_file = "/home/aatman/Documents/e-com-application/return_reporter/data/sku_mapping.csv"

        # Check if file exists
        if not os.path.exists(mapping_file):
            messagebox.showerror("Error", f"Mapping file not found:\n{mapping_file}")
            return
        
        
        # file = filedialog.askopenfilename(
        #     title="Select Return Data CSV",
        #     filetypes=[
        #         ("CSV files", "*.csv *.CSV"),
        #         ("All files", "*.*")
        #     ],
        #     initialdir=os.path.expanduser("~/Downloads")  # start in Downloads
        # )

        if mapping_file:
            self.mapping_path.set(mapping_file)

    def generate_report(self):
        returns_file = self.returns_path.get()
        mapping_file = self.mapping_path.get()

        if not returns_file or not mapping_file:
            messagebox.showerror("Error", "Please select both CSV files.")
            return

        try:
            output_path = generate_return_report(returns_file, mapping_file, self.output_dir)
            messagebox.showinfo("Success", f"✅ Report generated successfully!\n\nSaved at:\n{output_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report:\n\n{e}")

    def open_output_folder(self):
        if os.path.exists(self.output_dir):
            subprocess.Popen(["xdg-open", self.output_dir])
        else:
            messagebox.showerror("Error", "Output folder not found.")

if __name__ == "__main__":
    root = tk.Tk()
    app = ReturnReportApp(root)
    root.mainloop()
