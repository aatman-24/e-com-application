#!/usr/bin/env python3
"""
Daily Order Report Generator - Final Teal Theme (Option A v2)

Features:
- Minimal mac-like dark UI (teal theme)
- Panels: File Inputs, Actions, Log
- Auto-generate output to ~/Downloads/output/daily_report/
- Uses SKU mapping CSV and Orders CSV
- Run: python3 generate_order_report_ui.py

Dependencies:
    pip install pandas PyQt5
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

PROJECT_DIR = "/home/aatman/Documents/e-com-application/daily_order_report"
DEFAULT_ORDERS_PATH = os.path.expanduser("~/Downloads/orders.csv")
DEFAULT_SKU_MAP_PATH = os.path.join(PROJECT_DIR, "data/sku_mapping.csv")


def default_output_path():
    timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M")
    downloads_output = os.path.expanduser("~/Downloads/output/daily_report")
    os.makedirs(downloads_output, exist_ok=True)
    return os.path.join(downloads_output, f"order_report_{timestamp}.txt")

# ------------------------------
# Business logic helpers
# ------------------------------

def load_sku_mapping(csv_path: str):
    """Load mapping and build both forward and reverse lookups."""
    parent_to_children = defaultdict(list)
    child_to_parent = {}

    if not csv_path or not os.path.exists(csv_path):
        return {}, {}

    try:
        df = pd.read_csv(csv_path, dtype=str).fillna('')
    except Exception:
        return {}, {}

    if 'Parent_SKU' not in df.columns or 'Child_SKU' not in df.columns:
        return {}, {}

    for _, row in df.iterrows():
        parent = str(row.get('Parent_SKU', '')).strip()
        child = str(row.get('Child_SKU', '')).strip()
        if not parent or not child:
            continue
        parent_to_children[parent].append(child)
        child_to_parent[child] = parent

    # Ensure every parent also maps to itself
    for parent in list(parent_to_children.keys()):
        child_to_parent.setdefault(parent, parent)

    return dict(parent_to_children), dict(child_to_parent)


def find_parent_sku(sku: str, child_to_parent: dict) -> str:
    """Return the parent SKU if known, else self."""
    return child_to_parent.get(sku.strip(), sku.strip())

    mapping = defaultdict(list)
    if not csv_path or not os.path.exists(csv_path):
        return dict(mapping)
    try:
        df = pd.read_csv(csv_path, dtype=str)
    except Exception:
        return dict(mapping)
    if 'Parent_SKU' not in df.columns or 'Child_SKU' not in df.columns:
        return dict(mapping)
    for _, row in df.iterrows():
        parent = str(row.get('Parent_SKU', '')).strip()
        child = str(row.get('Child_SKU', '')).strip()
        if parent and child:
            mapping[parent].append(child)
    return dict(mapping)





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
    finished = QtCore.pyqtSignal(str, str)  # message, output_path
    progress = QtCore.pyqtSignal(str)

    def __init__(self, orders_path, sku_map_path, output_path):
        super().__init__()
        self.orders_path = orders_path
        self.sku_map_path = sku_map_path
        self.output_path = output_path

    def run(self):
        try:
            self.progress.emit(f"Loading SKU mapping from: {self.sku_map_path}")
            parent_map, reverse_map = load_sku_mapping(self.sku_map_path)
            self.progress.emit(f"Loaded {len(parent_map)} parent SKUs")

            if not os.path.exists(self.orders_path):
                self.finished.emit(f"ERROR: Orders file not found: {self.orders_path}", self.output_path)
                return

            df = pd.read_csv(self.orders_path, dtype=str)
            self.progress.emit(f"Total rows in orders file: {len(df)}")

            df_filtered = df[df.apply(include_row, axis=1)]
            self.progress.emit(f"Rows after applying status/packet rules: {len(df_filtered)}")

            report_data = defaultdict(lambda: defaultdict(int))
            skipped_count = 0

            for _, row in df_filtered.iterrows():
                raw_sku = str(row.get('SKU', '')).strip()
                sku = find_parent_sku(raw_sku, reverse_map)
                size = normalize_size(row.get('Size', ''))
                try:
                    qty = int(float(row.get('Quantity', 0)))
                except Exception:
                    qty = 0
                report_data[sku][size] += qty

            lines = []
            overall_total = 0
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
            self.finished.emit(msg, self.output_path)

        except Exception as e:
            self.finished.emit(f"ERROR: Exception during generation: {e}", self.output_path)

# ------------------------------
# UI (Option A - Teal polished)
# ------------------------------
class Panel(QtWidgets.QFrame):
    def __init__(self, title=None, parent=None):
        super().__init__(parent)
        self.setObjectName('panel')
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Raised)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        if title:
            label = QtWidgets.QLabel(title)
            label.setObjectName('panelTitle')
            label.setAlignment(QtCore.Qt.AlignLeft)
            self.layout.addWidget(label)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Daily Order Report Generator')
        self.resize(920, 660)
        self.last_output_path = None

        # Base palette
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(20, 40, 42))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor('#E8E8E8'))
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor('#1E2627'))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor('#232A2B'))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor('#E8E8E8'))
        self.setPalette(palette)

        # Central widget and layout
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Header
        header = QtWidgets.QLabel('Daily Order Report Generator')
        header.setObjectName('appHeader')
        header.setAlignment(QtCore.Qt.AlignCenter)
        main_layout.addWidget(header)

        # File inputs panel
        file_panel = Panel('File Inputs')
        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignLeft)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.orders_edit = QtWidgets.QLineEdit(DEFAULT_ORDERS_PATH)
        self.orders_edit.setMinimumHeight(40)
        self.orders_btn = QtWidgets.QPushButton('Browse')
        self.orders_btn.setFixedWidth(110)
        self.orders_btn.clicked.connect(self.browse_orders)
        h1 = QtWidgets.QHBoxLayout(); h1.addWidget(self.orders_edit); h1.addWidget(self.orders_btn)
        form.addRow('Orders CSV:', h1)

        self.sku_edit = QtWidgets.QLineEdit(DEFAULT_SKU_MAP_PATH)
        self.sku_edit.setMinimumHeight(40)
        self.sku_btn = QtWidgets.QPushButton('Browse')
        self.sku_btn.setFixedWidth(110)
        self.sku_btn.clicked.connect(self.browse_sku_map)
        h2 = QtWidgets.QHBoxLayout(); h2.addWidget(self.sku_edit); h2.addWidget(self.sku_btn)
        form.addRow('SKU Mapping CSV:', h2)

        file_panel.layout.addLayout(form)
        main_layout.addWidget(file_panel)

        # Actions panel
        actions_panel = Panel('Actions')
        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.setSpacing(12)

        self.generate_btn = QtWidgets.QPushButton('Generate Report')
        self.generate_btn.setMinimumHeight(46)
        self.generate_btn.clicked.connect(self.generate_report)
        actions_layout.addWidget(self.generate_btn)

        self.open_report_btn = QtWidgets.QPushButton('Open Report')
        self.open_report_btn.setMinimumHeight(46)
        self.open_report_btn.clicked.connect(self.open_report)
        actions_layout.addWidget(self.open_report_btn)

        self.open_folder_btn = QtWidgets.QPushButton('Open Output Folder')
        self.open_folder_btn.setMinimumHeight(46)
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        actions_layout.addWidget(self.open_folder_btn)

        actions_panel.layout.addLayout(actions_layout)
        main_layout.addWidget(actions_panel)

        # Log panel
        log_panel = Panel('Log')
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(300)
        mono = QtGui.QFont('Courier New', 11)
        self.log.setFont(mono)
        log_panel.layout.addWidget(self.log)
        main_layout.addWidget(log_panel)

        # Status bar
        self.status = QtWidgets.QStatusBar()
        self.setStatusBar(self.status)

        # Stylesheet (teal polished)
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
           
            QPushButton { background-color: rgb(40,120,130); color: white; border-radius: 8px; padding: 10px 18px; font-size: 11pt; }
            QPushButton:hover { background-color: rgb(55,145,155); }
            QPushButton:disabled { background-color: rgb(60,80,82); color: #9aa; }
            QTextEdit { background: #162022; color: #E8E8E8; border: 1px solid rgba(80,80,80,0.12); border-radius: 8px; padding: 8px; }
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

        # QLabel { color: #F0F0F0; font-size: 12pt; font-weight: bold; }

    # def browse_orders(self):
    #     downloads = os.path.expanduser('~/Downloads')
    #     path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select Orders CSV', downloads, 'CSV Files (*.csv);;All Files (*)')
    #     if path:
    #         self.orders_edit.setText(path)

    def browse_orders(self):
        downloads = os.path.expanduser('~/Downloads')
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            'Select Orders CSV files',
            downloads,
            'CSV Files (*.csv);;All Files (*)'
        )
        if paths:
            self.orders_edit.setText('; '.join(paths))


    def browse_sku_map(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select SKU Mapping CSV', os.path.dirname(DEFAULT_SKU_MAP_PATH), 'CSV Files (*.csv);;All Files (*)')
        if path:
            self.sku_edit.setText(path)

    def append_log(self, message: str):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log.append(f"[{ts}] {message}")

    def generate_report(self):
        # orders_path = self.orders_edit.text().strip()
        orders_paths = [p.strip() for p in self.orders_edit.text().split(';') if p.strip()]
        sku_map_path = self.sku_edit.text().strip()
        output_path = default_output_path()

        if not orders_path or not os.path.exists(orders_path):
            QtWidgets.QMessageBox.warning(self, 'Missing file', 'Orders CSV not found or path is empty.')
            return

        if not sku_map_path or not os.path.exists(sku_map_path):
            ret = QtWidgets.QMessageBox.question(self, 'SKU Map missing', 'SKU mapping file not found. Continue without mapping?', QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if ret == QtWidgets.QMessageBox.No:
                return

        self.generate_btn.setEnabled(False)
        self.append_log('Starting report generation...')
        self.status.showMessage('Generating...')

        # remember output for open actions
        self.last_output_path = output_path

        self.thread = QtCore.QThread()
        self.worker = ReportGenerator(orders_path, sku_map_path, output_path)
        self.worker.moveToThread(self.thread)
        self.worker.progress.connect(self.append_log)
        self.worker.finished.connect(self.on_finished)
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def on_finished(self, message, output_path):
        try:
            self.thread.quit(); self.thread.wait()
        except Exception:
            pass
        self.generate_btn.setEnabled(True)
        self.append_log(message)
        self.status.showMessage('Ready', 5000)
        if message.startswith('SUCCESS'):
            QtWidgets.QMessageBox.information(self, 'Done', message)

    def open_report(self):
        path = self.last_output_path or default_output_path()
        if not path or not os.path.exists(path):
            QtWidgets.QMessageBox.warning(self, 'Not found', 'Report file not found.')
            return
        try:
            subprocess.Popen(['xdg-open', path])
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Error', f'Could not open report: {e}')

    def open_output_folder(self):
        path = self.last_output_path or default_output_path()
        folder = os.path.dirname(path)
        if not os.path.exists(folder):
            QtWidgets.QMessageBox.warning(self, 'Not found', 'Output folder does not exist.')
            return
        try:
            subprocess.Popen(['xdg-open', folder])
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Error', f'Could not open folder: {e}')

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