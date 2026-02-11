#!/usr/bin/env python3

import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTextEdit, QMessageBox
)
from PyQt5.QtCore import Qt

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
BASE_DIR = Path("data")
DOWNLOADS_DIR = Path.home() / "Downloads"
SKU_PRICE_DEFAULT_DIR = Path.home() / "Documents" / "daily_payment_analysis"

# --------------------------------------------------
# MAIN UI
# --------------------------------------------------
class ProfitCalculatorUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SKU Profit Calculator")
        self.setMinimumSize(720, 520)

        self.sku_price_file = None
        self.order_files = []
        self.output_file = None

        self.build_ui()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------
    def build_ui(self):
        layout = QVBoxLayout()

        # ---------- SKU PRICE ----------
        btn_price = QPushButton("Select SKU Price File")
        btn_price.clicked.connect(self.select_price_file)
        self.lbl_price = QLabel("SKU Price File: Not selected")

        # ---------- ORDER FILES ----------
        btn_orders = QPushButton("Select Order Files")
        btn_orders.clicked.connect(self.select_order_files)
        self.lbl_orders = QLabel("Order Files: Not selected")

        # ---------- ACTIONS ----------
        self.btn_run = QPushButton("Generate Report")
        self.btn_run.setStyleSheet("font-weight: bold; padding: 8px;")
        self.btn_run.clicked.connect(self.run_report)

        self.btn_open_file = QPushButton("Open Generated Report")
        self.btn_open_file.setEnabled(False)
        self.btn_open_file.clicked.connect(self.open_output_file)

        # ---------- LOG ----------
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        # ---------- LAYOUT ----------
        layout.addWidget(btn_price)
        layout.addWidget(self.lbl_price)
        layout.addSpacing(10)

        layout.addWidget(btn_orders)
        layout.addWidget(self.lbl_orders)
        layout.addSpacing(20)

        layout.addWidget(self.btn_run)
        layout.addWidget(self.btn_open_file)
        layout.addSpacing(20)

        layout.addWidget(QLabel("Logs"))
        layout.addWidget(self.log)

        self.setLayout(layout)

    # --------------------------------------------------
    # UTIL
    # --------------------------------------------------
    def log_msg(self, msg):
        self.log.append(msg)
        self.log.verticalScrollBar().setValue(
            self.log.verticalScrollBar().maximum()
        )

    # --------------------------------------------------
    # FILE PICKERS
    # --------------------------------------------------
    def select_price_file(self):
        dialog = QFileDialog(self, "Select SKU Price File")
        dialog.setDirectory(str(SKU_PRICE_DEFAULT_DIR))
        dialog.setNameFilter("CSV Files (*.csv);;All Files (*)")
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)  # 🔥 KEY FIX

        if dialog.exec_():
            files = dialog.selectedFiles()
            if files:
                self.sku_price_file = Path(files[0])
                self.lbl_price.setText(f"SKU Price File: {files[0]}")
                self.log_msg("✔ SKU price file selected")



    def select_order_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Order Files",
            str(DOWNLOADS_DIR),          # ✅ Default Downloads
            "Excel Files (*.xlsx)"
        )
        if files:
            self.order_files = [Path(f) for f in files]
            self.lbl_orders.setText(f"Order Files Selected: {len(files)}")
            self.log_msg(f"✔ {len(files)} order files selected")

    # --------------------------------------------------
    # ACTIONS
    # --------------------------------------------------
    def run_report(self):
        if not self.sku_price_file:
            QMessageBox.warning(self, "Missing File", "Please select SKU price file")
            return

        if not self.order_files:
            QMessageBox.warning(self, "Missing Files", "Please select order files")
            return

        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")

        # ✅ Output goes next to sku_price.csv
        output_dir = self.sku_price_file.parent
        self.output_file = output_dir / f"sku_profit_report_{timestamp}.xlsx"

        try:
            self.log_msg("▶ Starting report generation...")
            self.log_msg(f"📄 Output file: {self.output_file}")

            cmd = [sys.executable, "sku_profit_cal_multi_svc.py"]

            env = dict(os.environ)
            env["SKU_PRICE_FILE"] = str(self.sku_price_file)
            env["ORDER_FILES"] = ";".join(str(f) for f in self.order_files)
            env["OUTPUT_FILE"] = str(self.output_file)

            subprocess.run(cmd, check=True, env=env)

            self.log_msg("✅ Report generated successfully")
            self.log_msg(f"📄 Saved at: {self.output_file}")

            self.btn_open_file.setEnabled(True)

        except subprocess.CalledProcessError as e:
            self.log_msg("❌ Error occurred")
            self.log_msg(str(e))


    def open_output_file(self):
        if self.output_file and self.output_file.exists():
            subprocess.run(["xdg-open", str(self.output_file)])
        else:
            QMessageBox.information(self, "Not Found", "Output file not found")

# --------------------------------------------------
# RUN APP
# --------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ProfitCalculatorUI()
    win.show()
    sys.exit(app.exec_())
