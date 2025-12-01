#!/usr/bin/env python3
"""
Order Report Generator - PyQt5 Desktop UI (Enhanced)

Enhancements:
1. Default CSV file picker opens in Downloads folder.
2. Generated report name = Current date (DD-MM-YYYY_HH:SS).txt
3. Fixed default SKU mapping path = ./data/sku_mapping.csv (relative to project).
4. SKU mapping can still be changed via file picker.
"""

import sys
import os
import subprocess
from collections import defaultdict
from datetime import datetime

import pandas as pd
from PyQt5 import QtCore, QtGui, QtWidgets

# ------------------------------
# Configuration / Mappings
# ------------------------------
SIZE_MAPPING = {
    "6-12": "1-2", "0-1": "1-2", "1-2": "1-2",
    "2-3": "3-4", "3-4": "3-4",
    "4-5": "5-6", "5-6": "5-6",
    "6-7": "7-8", "7-8": "7-8",
    "8-9": "9-10", "9-10": "9-10",
    "10-11": "11-12", "11-12": "11-12",
    "12-13": "13-14", "13-14": "13-14", "14-15": "13-14"
}

PRODUCTION_SIZE_ORDER = ["1-2", "3-4", "5-6", "7-8", "9-10", "11-12", "13-14"]

# Project root
PROJECT_DIR = "/home/aatman/Documents/e-com-application/daily_order_report"
DEFAULT_ORDERS_PATH = os.path.expanduser("~/Downloads/orders.csv")
DEFAULT_SKU_MAP_PATH = os.path.join(PROJECT_DIR, "data/sku_mapping.csv")

def default_output_path():
    timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M")
    return os.path.join(PROJECT_DIR, f"order_report_{timestamp}.txt")

# ------------------------------
# Helper Functions
# ------------------------------

def load_sku_mapping(csv_path: str) -> dict:
    mapping = defaultdict(list)
    if not csv_path or not os.path.exists(csv_path):
        return dict(mapping)
    try:
        df = pd.read_csv(csv_path, dtype=str)
    except Exception:
        return dict(mapping)

    if 'parent_sku' not in df.columns or 'child_sku' not in df.columns:
        return dict(mapping)

    for _, row in df.iterrows():
        parent = str(row.get('parent_sku', '')).strip()
        child = str(row.get('child_sku', '')).strip()
        if parent and child:
            mapping[parent].append(child)
    return dict(mapping)


def find_parent_sku(sku: str, sku_map: dict) -> str:
    sku = sku.strip()
    for parent, children in sku_map.items():
        if sku in children:
            return parent
    return sku


def normalize_size(size: str) -> str:
    if pd.isna(size):
        return str(size)
    s = str(size).strip().lower()
    s = s.replace('years', '').replace('year', '').replace('yrs', '')
    s = s.replace('months', '').replace('month', '').replace('m', '')
    s = s.replace(' ', '').replace('+', '').replace('/', '-')
    if s in ('6-12', '0-6', '0-1', '9-12'):
        s = '1-2'
    mapped = SIZE_MAPPING.get(s, s)
    return mapped


def include_row(row) -> bool:
    status = str(row.get('Reason for Credit Entry', '')).strip().upper()
    packet_id = row.get('Packet Id', '')
    packet_id_str = '' if pd.isna(packet_id) else str(packet_id).strip()

    if status == 'CANCELLED':
        return False
    if status in ('PENDING', 'HOLD'):
        return True
    if status == 'READY_TO_SHIP':
        return packet_id_str == '' or packet_id_str.lower() in ('nan', 'none')
    return False

# ------------------------------
# Worker
# ------------------------------
class ReportGenerator(QtCore.QObject):
    finished = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(str)

    def __init__(self, orders_path, sku_map_path, output_path):
        super().__init__()
        self.orders_path = orders_path
        self.sku_map_path = sku_map_path
        self.output_path = output_path

    def run(self):
        try:
            self.progress.emit(f"Loading SKU mapping from: {self.sku_map_path}")
            sku_map = load_sku_mapping(self.sku_map_path)
            self.progress.emit(f"Loaded {len(sku_map)} parent SKUs")

            if not os.path.exists(self.orders_path):
                self.finished.emit(f"ERROR: Orders file not found: {self.orders_path}")
                return

            df = pd.read_csv(self.orders_path, dtype=str)
            self.progress.emit(f"Total rows in orders file: {len(df)}")

            df_filtered = df[df.apply(include_row, axis=1)]
            self.progress.emit(f"Rows after applying status/packet rules: {len(df_filtered)}")

            report_data = defaultdict(lambda: defaultdict(int))
            skipped_count = 0

            for _, row in df_filtered.iterrows():
                raw_sku = str(row.get('SKU', '')).strip()
                sku = find_parent_sku(raw_sku, sku_map)
                size = normalize_size(row.get('Size', ''))
                try:
                    qty = int(float(row.get('Quantity', 0)))
                except Exception:
                    qty = 0
                report_data[sku][size] += qty

            lines, overall_total = [], 0
            for sku, size_dict in report_data.items():
                total_pieces = sum(size_dict.values())
                if total_pieces == 0:
                    skipped_count += 1
                    continue

                lines.append(f"SKU: {sku}")
                lines.append('-' * 40)
                for size in PRODUCTION_SIZE_ORDER:
                    if size in size_dict:
                        qty = size_dict[size]
                        lines.append(f"{size} ({qty})")
                lines.append('---')
                lines.append(f"TOTAL PIECES: {total_pieces}\n\n\n")
                overall_total += total_pieces

            lines.append('=' * 40)
            lines.append(f"OVERALL TOTAL PIECES: {overall_total}")
            lines.append('=' * 40)

            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(f"Report generated: {datetime.now().isoformat()}\n\n")
                f.write('\n'.join(lines))

            msg = f"SUCCESS: Report saved to {self.output_path}. SKUs skipped (zero total): {skipped_count}"
            self.finished.emit(msg)

        except Exception as e:
            self.finished.emit(f"ERROR: Exception during generation: {e}")

# ------------------------------
# UI
# ------------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Order Report Generator')
        self.resize(800, 600)
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        form = QtWidgets.QFormLayout()

        self.orders_edit = QtWidgets.QLineEdit(DEFAULT_ORDERS_PATH)
        self.orders_btn = QtWidgets.QPushButton('Browse')
        self.orders_btn.clicked.connect(self.browse_orders)
        h1 = QtWidgets.QHBoxLayout(); h1.addWidget(self.orders_edit); h1.addWidget(self.orders_btn)
        form.addRow('Orders CSV:', h1)

        self.sku_edit = QtWidgets.QLineEdit(DEFAULT_SKU_MAP_PATH)
        self.sku_btn = QtWidgets.QPushButton('Browse')
        self.sku_btn.clicked.connect(self.browse_sku_map)
        h2 = QtWidgets.QHBoxLayout(); h2.addWidget(self.sku_edit); h2.addWidget(self.sku_btn)
        form.addRow('SKU Mapping CSV:', h2)

        self.output_edit = QtWidgets.QLineEdit(default_output_path())
        self.output_btn = QtWidgets.QPushButton('Browse')
        self.output_btn.clicked.connect(self.browse_output)
        h3 = QtWidgets.QHBoxLayout(); h3.addWidget(self.output_edit); h3.addWidget(self.output_btn)
        form.addRow('Output Report (.txt):', h3)

        layout.addLayout(form)

        btn_layout = QtWidgets.QHBoxLayout()
        self.generate_btn = QtWidgets.QPushButton('Generate Report')
        self.generate_btn.clicked.connect(self.generate_report)
        btn_layout.addWidget(self.generate_btn)

        self.open_report_btn = QtWidgets.QPushButton('Open Report')
        self.open_report_btn.clicked.connect(self.open_report)
        btn_layout.addWidget(self.open_report_btn)

        self.open_folder_btn = QtWidgets.QPushButton('Open Output Folder')
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        btn_layout.addWidget(self.open_folder_btn)
        layout.addLayout(btn_layout)

        self.log = QtWidgets.QTextEdit(); self.log.setReadOnly(True)
        font = QtGui.QFont('Courier', 10)
        self.log.setFont(font)
        layout.addWidget(self.log)

        self.status = QtWidgets.QStatusBar(); self.setStatusBar(self.status)

    def browse_orders(self):
        downloads = os.path.expanduser('~/Downloads')
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select Orders CSV', downloads, 'CSV Files (*.csv);;All Files (*)')
        if path: self.orders_edit.setText(path)

    def browse_sku_map(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select SKU Mapping CSV', os.path.dirname(DEFAULT_SKU_MAP_PATH), 'CSV Files (*.csv);;All Files (*)')
        if path: self.sku_edit.setText(path)

    def browse_output(self):
        project_path = PROJECT_DIR
        timestamp = datetime.now().strftime('%d-%m-%Y_%H-%M')
        suggested = os.path.join(project_path, f'order_report_{timestamp}.txt')
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Select Output Report File', suggested, 'Text Files (*.txt);;All Files (*)')
        if path: self.output_edit.setText(path)

    def append_log(self, message: str):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log.append(f"[{ts}] {message}")

    def generate_report(self):
        orders_path = self.orders_edit.text().strip()
        sku_map_path = self.sku_edit.text().strip()
        output_path = self.output_edit.text().strip()

        if not orders_path or not os.path.exists(orders_path):
            QtWidgets.QMessageBox.warning(self, 'Missing file', 'Orders CSV not found or path is empty.')
            return

        if not sku_map_path or not os.path.exists(sku_map_path):
            ret = QtWidgets.QMessageBox.question(self, 'SKU Map missing', 'SKU mapping file not found. Continue without mapping?', QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if ret == QtWidgets.QMessageBox.No: return

        self.generate_btn.setEnabled(False)
        self.append_log('Starting report generation...')
        self.status.showMessage('Generating...')

        self.thread = QtCore.QThread()
        self.worker = ReportGenerator(orders_path, sku_map_path, output_path)
        self.worker.moveToThread(self.thread)
        self.worker.progress.connect(self.append_log)
        self.worker.finished.connect(self.on_finished)
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def on_finished(self, message):
        try:
            self.thread.quit(); self.thread.wait()
        except Exception: pass
        self.generate_btn.setEnabled(True)
        self.append_log(message)
        self.status.showMessage('Ready', 5000)
        if message.startswith('SUCCESS'):
            QtWidgets.QMessageBox.information(self, 'Done', message)

    def open_report(self):
        path = self.output_edit.text().strip()
        if not path or not os.path.exists(path):
            QtWidgets.QMessageBox.warning(self, 'Not found', 'Report file not found.'); return
        try: subprocess.Popen(['xdg-open', path])
        except Exception as e: QtWidgets.QMessageBox.warning(self, 'Error', f'Could not open report: {e}')

    def open_output_folder(self):
        path = self.output_edit.text().strip()
        if not path: QtWidgets.QMessageBox.warning(self, 'Missing', 'Please select an output file first.'); return
        folder = os.path.dirname(path)
        if not os.path.exists(folder): QtWidgets.QMessageBox.warning(self, 'Not found', 'Output folder does not exist.'); return
        try: subprocess.Popen(['xdg-open', folder])
        except Exception as e: QtWidgets.QMessageBox.warning(self, 'Error', f'Could not open folder: {e}')

# ------------------------------
# Main
# ------------------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()