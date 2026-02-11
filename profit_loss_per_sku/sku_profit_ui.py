#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QFileDialog, QTextEdit, QVBoxLayout, QHBoxLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QStandardPaths



SCRIPT_PATH = Path(__file__).parent / "sku_profit_analysis_order_level_v2.py"


class ProfitUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SKU Profit & Return Analysis")
        self.setMinimumSize(600, 400)

        self.order_file = ""
        self.return_file = ""
        self.buying_file = ""

        self._build_ui()

    def downloads_dir(self):
        return QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
    

    def buying_price_dir(self):
        return str(Path.home() / "Documents" / "profit_loss_per_sku")

    def _build_ui(self):
        layout = QVBoxLayout()

        # ---- Order file
        self.lbl_order = QLabel("Order CSV: Not selected")
        btn_order = QPushButton("Select Order File")
        btn_order.clicked.connect(self.select_order)

        # ---- Return file
        self.lbl_return = QLabel("Return CSV: Not selected")
        btn_return = QPushButton("Select Return File")
        btn_return.clicked.connect(self.select_return)

        # ---- Buying price file
        self.lbl_buying = QLabel("Buying Price CSV: Not selected")
        btn_buying = QPushButton("Select Buying Price File")
        btn_buying.clicked.connect(self.select_buying)

        # ---- Run
        btn_run = QPushButton("Run Analysis")
        btn_run.setStyleSheet("font-weight: bold; height: 40px;")
        btn_run.clicked.connect(self.run_analysis)

        # ---- Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        # ---- Layout
        for w in [
            self.lbl_order, btn_order,
            self.lbl_return, btn_return,
            self.lbl_buying, btn_buying,
            btn_run,
            QLabel("Logs:"),
            self.log
        ]:
            layout.addWidget(w)

        self.setLayout(layout)

    def select_order(self):
        f, _ = QFileDialog.getOpenFileName(
                self,
                "Select Order CSV",
                self.downloads_dir(),
                "CSV Files (*.csv)"
            )
        if f:
            self.order_file = f
            self.lbl_order.setText(f"Order CSV: {Path(f).name}")

    def select_return(self):
        f, _ = QFileDialog.getOpenFileName(
                self,
                "Select Order CSV",
                self.downloads_dir(),
                "CSV Files (*.csv)"
        )
        if f:
            self.return_file = f
            self.lbl_return.setText(f"Return CSV: {Path(f).name}")

    def select_buying(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Select Buying Price CSV",
            self.buying_price_dir(),
            "CSV Files (*.csv)"
        )
        if f:
            self.buying_file = f
            self.lbl_buying.setText(f"Buying Price CSV: {Path(f).name}")

    def run_analysis(self):
        if not all([self.order_file, self.return_file, self.buying_file]):
            msg = "❌ Please select all files first."
            print(msg)
            self.log.append(msg)
            return

        self.log.append("▶ Running analysis...")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                ],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **dict(**dict()),
                    "ORDER_FILE": self.order_file,
                    "RETURN_FILE": self.return_file,
                    "BUYING_PRICE_FILE": self.buying_file,
                }
            )

            # Print to terminal
            if result.stdout:
                print(result.stdout)
                self.log.append(result.stdout)

            self.log.append("✅ Analysis completed successfully.")
            self.log.append("📄 Output file generated in script directory.")

        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Error occurred:\n{e.stderr or e}"
            print(error_msg)          # terminal
            self.log.append(error_msg)  # UI console


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProfitUI()
    window.show()
    sys.exit(app.exec_())
