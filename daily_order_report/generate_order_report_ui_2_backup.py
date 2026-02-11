#!/usr/bin/env python3
"""
Daily Order Report Generator - Final Teal Theme (Multi Orders CSV, UI FIXED)

- UI unchanged (3 action buttons restored)
- Multiple Orders CSV selection
- Single consolidated output report
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

PRODUCTION_SIZE_ORDER = ["1-2", "3-4", "5-6", "7-8", "9-10", "11-12", "13-14", "m", "M"] 

PROJECT_DIR = "/home/aatman/Documents/e-com-application/daily_order_report"
DEFAULT_ORDERS_PATH = os.path.expanduser("~/Downloads/orders.csv")
DEFAULT_SKU_MAP_PATH = os.path.join(PROJECT_DIR, "data/sku_mapping.csv")


def default_output_path():
    ts = datetime.now().strftime("%d-%m-%Y_%H-%M")
    out_dir = os.path.expanduser("~/Downloads/output/daily_report")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f"order_report_{ts}.txt")

# ------------------------------
# Business logic helpers
# ------------------------------
def load_sku_mapping(csv_path):
    parent_to_children = defaultdict(list)
    child_to_parent = {}

    if not csv_path or not os.path.exists(csv_path):
        return {}, {}

    df = pd.read_csv(csv_path, dtype=str).fillna('')

    for _, row in df.iterrows():
        parent = row.get('Parent_SKU', '').strip()
        child = row.get('Child_SKU', '').strip()
        if parent and child:
            parent_to_children[parent].append(child)
            child_to_parent[child] = parent

    for p in parent_to_children:
        child_to_parent.setdefault(p, p)

    return dict(parent_to_children), dict(child_to_parent)


def find_parent_sku(sku, child_to_parent):
    return child_to_parent.get(sku.strip(), sku.strip())


def normalize_size(size):
    if pd.isna(size):
        return None

    s = str(size).strip()
    if not s or s.lower() == 'nan':
        return None

    raw = s  # preserve original for non-year sizes

    s = s.lower()
    s = s.replace('years', '').replace('year', '')
    s = s.replace('months', '').replace('month', '')
    s = s.replace('yrs', '')
    s = s.replace(' ', '').replace('+', '').replace('/', '-')

    # map only if year-based
    mapped = SIZE_MAPPING.get(s)
    return mapped if mapped else raw



def include_row(row):
    status = str(row.get('Reason for Credit Entry', '')).upper().strip()
    packet_id = str(row.get('Packet Id', '')).strip().lower()

    if status in ('CANCELLED', 'HOLD'):
        return False
    if status in ('PENDING'):
        return True
    if status == 'READY_TO_SHIP':
        return packet_id in ('', 'nan', 'none')
    return False

# ------------------------------
# Worker
# ------------------------------
class ReportGenerator(QtCore.QObject):
    finished = QtCore.pyqtSignal(str, str)
    progress = QtCore.pyqtSignal(str)

    def __init__(self, orders_paths, sku_map_path, output_path):
        super().__init__()
        self.orders_paths = orders_paths
        self.sku_map_path = sku_map_path
        self.output_path = output_path

    def run(self):
        try:
            self.progress.emit(f"Loading SKU mapping from: {self.sku_map_path}")
            _, reverse_map = load_sku_mapping(self.sku_map_path)

            dfs = []
            for path in self.orders_paths:
                self.progress.emit(f"Loading orders files: {path}")
                try:
                    dfs.append(pd.read_csv(path, dtype=str))
                except Exception as e:
                    self.progress.emit(f"⚠️ Failed to read {path}: {e}")

            if not dfs:
                self.finished.emit("ERROR: No valid orders files loaded.", self.output_path)
                return

            df = pd.concat(dfs, ignore_index=True)
            self.progress.emit(f"Total rows after merging files: {len(df)}")

            df = df[df.apply(include_row, axis=1)]
            self.progress.emit(f"Rows after applying status/packet rules: {len(df)}")

            report_data = defaultdict(lambda: defaultdict(int))

            for _, row in df.iterrows():
                sku = find_parent_sku(str(row.get('SKU', '')).strip(), reverse_map)
                size = normalize_size(row.get('Size', ''))
                if not size:
                    continue
                try:
                    qty = int(float(row.get('Quantity', 0)))
                except Exception:
                    qty = 0
                report_data[sku][size] += qty

            lines = []
            overall_total = 0

            for sku, size_dict in report_data.items():
                total = sum(size_dict.values())
                if total == 0:
                    continue

                lines.append(f"SKU: {sku}")
                lines.append('-' * 40)

                # for size in PRODUCTION_SIZE_ORDER:
                #     if size in size_dict:
                #         lines.append(f"{size} ({size_dict[size]})")

                # 1. Print known production sizes first (ordered)
                printed_sizes = set()

                for size in PRODUCTION_SIZE_ORDER:
                    if size in size_dict:
                        lines.append(f"{size} ({size_dict[size]})")
                        printed_sizes.add(size)

                # 2. Print remaining sizes as-is (M, L, XL, Free Size, etc.)
                other_sizes = sorted(s for s in size_dict if s not in printed_sizes)

                for size in other_sizes:
                    lines.append(f"{size} ({size_dict[size]})")


                lines.append('---')
                lines.append(f"TOTAL PIECES: {total}\n\n")
                overall_total += total

            lines.append('=' * 40)
            lines.append(f"OVERALL TOTAL PIECES: {overall_total}")
            lines.append('=' * 40)

            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(f"Report generated: {datetime.now().isoformat()}\n\n")
                f.write('\n'.join(lines))

            self.finished.emit(f"SUCCESS: Report saved to {self.output_path}", self.output_path)

        except Exception as e:
            self.finished.emit(f"ERROR: {e}", self.output_path)

# ------------------------------
# UI (UNCHANGED)
# ------------------------------
class Panel(QtWidgets.QFrame):
    def __init__(self, title=None, parent=None):
        super().__init__(parent)
        self.setObjectName('panel')
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        if title:
            label = QtWidgets.QLabel(title)
            label.setObjectName('panelTitle')
            self.layout.addWidget(label)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Daily Order Report Generator')
        self.resize(920, 660)
        self.last_output_path = None

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)

        header = QtWidgets.QLabel('Daily Order Report Generator')
        header.setObjectName('appHeader')
        header.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(header)

        # File Inputs
        file_panel = Panel('File Inputs')
        form = QtWidgets.QFormLayout()

        self.orders_edit = QtWidgets.QLineEdit(DEFAULT_ORDERS_PATH)
        self.orders_btn = QtWidgets.QPushButton('Browse')
        self.orders_btn.clicked.connect(self.browse_orders)
        h1 = QtWidgets.QHBoxLayout()
        h1.addWidget(self.orders_edit)
        h1.addWidget(self.orders_btn)
        form.addRow('Orders CSV:', h1)

        self.sku_edit = QtWidgets.QLineEdit(DEFAULT_SKU_MAP_PATH)
        self.sku_btn = QtWidgets.QPushButton('Browse')
        self.sku_btn.clicked.connect(self.browse_sku_map)
        h2 = QtWidgets.QHBoxLayout()
        h2.addWidget(self.sku_edit)
        h2.addWidget(self.sku_btn)
        form.addRow('SKU Mapping CSV:', h2)

        file_panel.layout.addLayout(form)
        main_layout.addWidget(file_panel)

        # Actions
        actions_panel = Panel('Actions')
        actions_layout = QtWidgets.QHBoxLayout()

        self.generate_btn = QtWidgets.QPushButton('Generate Report')
        self.generate_btn.clicked.connect(self.generate_report)
        actions_layout.addWidget(self.generate_btn)

        self.open_report_btn = QtWidgets.QPushButton('Open Report')
        self.open_report_btn.clicked.connect(self.open_report)
        actions_layout.addWidget(self.open_report_btn)

        self.open_folder_btn = QtWidgets.QPushButton('Open Output Folder')
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        actions_layout.addWidget(self.open_folder_btn)

        actions_panel.layout.addLayout(actions_layout)
        main_layout.addWidget(actions_panel)

        # Log
        log_panel = Panel('Log')
        self.log = QtWidgets.QTextEdit(readOnly=True)
        log_panel.layout.addWidget(self.log)
        main_layout.addWidget(log_panel)


        self.setStyleSheet("""
            QMainWindow { background: rgba(19,23,28,1); }
            QLabel#appHeader { font-size: 18pt; font-weight: 600; color: #F5F5F5; padding: 6px; }

            QFrame#panel {
                background: rgba(28, 32, 38, 1);
                border: 1px solid rgba(100, 100, 100, 0.18);
                border-radius: 10px;
            }
            QLabel#panelTitle { color: #D6E6E6; font-weight: 500; margin-bottom: 6px; }

            QLineEdit {
                background: rgba(30, 34, 40, 1);
                color: #E8E8E8;
                border: 1px solid rgba(80, 80, 80, 0.2);
                border-radius: 8px;
                padding: 10px;
                font-size: 11pt;
            }

            QPushButton {
                background-color: rgb(40,120,130);
                color: white;
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 11pt;
            }
            QPushButton:hover { background-color: rgb(55,145,155); }
            QPushButton:disabled { background-color: rgb(60,80,82); color: #9aa; }

            QTextEdit {
                background: #162022;
                color: #E8E8E8;
                border: 1px solid rgba(80,80,80,0.12);
                border-radius: 8px;
                padding: 8px;
            }

            QLabel { color: #E8E8E8; font-size: 13pt; font-weight: 600; }

            QMessageBox {
                background-color: rgba(28, 32, 38, 1);
                color: #E8E8E8;
            }

            QMessageBox QLabel {
                color: #E8E8E8;
                font-size: 11pt;
            }

            QMessageBox QPushButton {
                background-color: rgb(40, 120, 130);
                color: white;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 10pt;
            }

            QMessageBox QPushButton:hover {
                background-color: rgb(55, 145, 155);
            }
        """)


    def browse_orders(self):
        downloads = os.path.expanduser('~/Downloads')
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, 'Select Orders CSV files', downloads, 'CSV Files (*.csv)'
        )
        if paths:
            self.orders_edit.setText('; '.join(paths))

    def browse_sku_map(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Select SKU Mapping CSV', '', 'CSV Files (*.csv)'
        )
        if path:
            self.sku_edit.setText(path)

    def append_log(self, msg):
        self.log.append(msg)

    def generate_report(self):
        orders_paths = [p.strip() for p in self.orders_edit.text().split(';') if p.strip()]
        if not orders_paths:
            QtWidgets.QMessageBox.warning(self, 'Missing file', 'Please select at least one Orders CSV.')
            return

        output_path = default_output_path()
        self.last_output_path = output_path

        self.thread = QtCore.QThread()
        self.worker = ReportGenerator(orders_paths, self.sku_edit.text(), output_path)
        self.worker.moveToThread(self.thread)

        self.worker.progress.connect(self.append_log)
        self.worker.finished.connect(self.on_finished)
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def on_finished(self, msg, _):
        self.thread.quit()
        self.thread.wait()
        QtWidgets.QMessageBox.information(self, 'Done', msg)

    def open_report(self):
        if not self.last_output_path or not os.path.exists(self.last_output_path):
            QtWidgets.QMessageBox.warning(self, 'Not found', 'Report file not found.')
            return
        subprocess.Popen(['xdg-open', self.last_output_path])

    def open_output_folder(self):
        if not self.last_output_path:
            QtWidgets.QMessageBox.warning(self, 'Not found', 'No output generated yet.')
            return
        folder = os.path.dirname(self.last_output_path)
        subprocess.Popen(['xdg-open', folder])


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
