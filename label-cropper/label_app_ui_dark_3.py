#!/usr/bin/env python3
"""
label_app_modern_ui_v2.py
Modern/dark card-style UI close to the provided screenshot.
Uses existing functions in label_processor.py (unchanged):
 - merge_input_pdfs
 - sort_pdf_by_parent_sku
 - crop_and_fit_labels
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QTextEdit, QFileDialog, QHBoxLayout, QVBoxLayout, QFrame, QSizePolicy,
    QSpacerItem, QMessageBox
)

# import existing business logic (must remain unchanged)
from label_processor import (
    merge_input_pdfs,
    sort_pdf_by_parent_sku,
    crop_and_fit_labels,
)


# -----------------------
# Worker runs the processing steps in background thread
# -----------------------
class Worker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(str)    # final output path
    error = pyqtSignal(str)

    def __init__(self, files, sku_csv):
        super().__init__()
        self.files = list(files)
        self.sku_csv = sku_csv

    def run(self):
        try:
            now = datetime.now()
            date_str = now.strftime("%d-%b-%Y").lower()
            hour_str = now.strftime("%H%M%S")

            out_dir = Path.home() / "Downloads" / "output"
            out_dir.mkdir(parents=True, exist_ok=True)

            merged = str(out_dir / f"{date_str}_merged_{hour_str}.pdf")
            sorted_pdf = str(out_dir / f"{date_str}_sorted_{hour_str}.pdf")
            final_pdf = str(out_dir / f"{date_str}_label_{hour_str}.pdf")

            self.log.emit(f"Step 1 — merging {len(self.files)} file(s)...")
            merge_input_pdfs(self.files, merged)

            if self.sku_csv and os.path.exists(self.sku_csv):
                self.log.emit("Step 2 — sorting by SKU mapping...")
                sort_pdf_by_parent_sku(merged, self.sku_csv, sorted_pdf)
                crop_input = sorted_pdf
            else:
                self.log.emit("Step 2 — SKU mapping missing; skipping sort.")
                crop_input = merged

            self.log.emit("Step 3 — cropping & fitting labels (100×100 mm)...")
            crop_and_fit_labels(crop_input, final_pdf)

            # remove temp files if present
            for tmp in (merged, sorted_pdf):
                try:
                    if os.path.exists(tmp) and tmp != final_pdf:
                        os.remove(tmp)
                except Exception:
                    pass

            self.log.emit("Completed.")
            self.finished.emit(final_pdf)
        except Exception as e:
            self.error.emit(str(e))


# -----------------------
# Drop area widget (dashed box)
# -----------------------
class DropArea(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        label = QLabel("Drag and drop PDF files here\nor click to upload", self)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet("color: #95a0a6;")
        label.setFont(QFont("Segoe UI", 14))
        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(label, alignment=Qt.AlignCenter)
        layout.addStretch()
        self.setLayout(layout)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        files = []
        for u in urls:
            p = u.toLocalFile()
            if p.lower().endswith(".pdf") and os.path.exists(p):
                files.append(p)
        if files:
            self.parent().add_files(files)

    def mousePressEvent(self, event):
        # delegate to parent's upload dialog
        self.parent().on_upload_clicked()


# -----------------------
# Main application window
# -----------------------
class LabelApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Label Generator")
        self.setMinimumSize(1100, 720)
        self.setWindowIcon(QIcon.fromTheme("document-new"))

        base = os.path.dirname(os.path.abspath(__file__))
        self.default_sku = os.path.join(base, "data", "sku_mapping.csv")
        self.sku_path = self.default_sku
        self.selected_files = []

        self.worker = None
        self.worker_thread = None

        self._build_ui()
        self._apply_style()
        self._refresh_sku_indicator()

    def _build_ui(self):
        root = QVBoxLayout()
        root.setSpacing(18)
        root.setContentsMargins(18, 18, 18, 18)
        self.setLayout(root)

        # Title (centered)
        title = QLabel("Label Generator")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setFixedHeight(56)
        root.addWidget(title)

        # Cards horizontal
        cards = QHBoxLayout()
        cards.setSpacing(18)
        root.addLayout(cards)

        # Left card (upload)
        left_card = QFrame()
        left_card.setObjectName("card")
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(12)
        left_card.setLayout(left_layout)
        left_card.setMinimumWidth(720)

        left_header = QLabel("Upload Files")
        left_header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        left_layout.addWidget(left_header)

        # Drop area
        self.drop_area = DropArea(self)
        self.drop_area.setFixedHeight(360)
        left_layout.addWidget(self.drop_area)

        # File list (below drop area)
        self.file_list = QListWidget()
        self.file_list.setFixedHeight(96)
        left_layout.addWidget(self.file_list)

        # Full width Clear button (large)
        self.btn_clear = QPushButton("🧹  Clear Files")
        self.btn_clear.setFixedHeight(48)
        self.btn_clear.clicked.connect(self.on_clear)
        left_layout.addWidget(self.btn_clear)

        cards.addWidget(left_card, 2)

        # Right card (actions)
        right_card = QFrame()
        right_card.setObjectName("card")
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(14)
        right_card.setLayout(right_layout)
        right_card.setMinimumWidth(340)

        right_header = QLabel("Actions")
        right_header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        right_layout.addWidget(right_header)

        # SKU mapping subcard
        sku_card = QFrame()
        sku_card.setObjectName("subcard")
        sku_layout = QVBoxLayout()
        sku_layout.setContentsMargins(12, 12, 12, 12)
        sku_layout.setSpacing(8)
        sku_card.setLayout(sku_layout)

        self.lbl_sku_status = QLabel("")  # will be set by _refresh_sku_indicator
        self.lbl_sku_status.setFont(QFont("Segoe UI", 12))
        sku_layout.addWidget(self.lbl_sku_status)

        self.btn_select_sku = QPushButton("🧾  Select SKU Mapping File")
        self.btn_select_sku.setFixedHeight(44)
        self.btn_select_sku.clicked.connect(self.on_select_sku)
        sku_layout.addWidget(self.btn_select_sku)

        right_layout.addWidget(sku_card)

        # Actions subcard
        actions_card = QFrame()
        actions_card.setObjectName("subcard")
        actions_layout = QVBoxLayout()
        actions_layout.setContentsMargins(12, 12, 12, 12)
        actions_layout.setSpacing(10)
        actions_card.setLayout(actions_layout)

        self.btn_generate = QPushButton("🚀  Generate")
        self.btn_generate.setFixedHeight(56)
        self.btn_generate.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.btn_generate.clicked.connect(self.on_generate)
        actions_layout.addWidget(self.btn_generate)

        self.btn_open_output = QPushButton("📁  Open Output Folder")
        self.btn_open_output.setFixedHeight(48)
        self.btn_open_output.clicked.connect(self.on_open_output)
        actions_layout.addWidget(self.btn_open_output)

        right_layout.addWidget(actions_card)
        right_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        cards.addWidget(right_card, 1)

        # Logs header
        logs_label = QLabel("Logs:")
        logs_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        root.addWidget(logs_label)

        # Two-column logs (left small, right main)
        logs_area = QHBoxLayout()
        logs_area.setSpacing(12)
        root.addLayout(logs_area)

        self.small_log = QTextEdit()
        self.small_log.setReadOnly(True)
        self.small_log.setFixedWidth(360)
        self.small_log.setFixedHeight(120)
        logs_area.addWidget(self.small_log)

        self.main_log = QTextEdit()
        self.main_log.setReadOnly(True)
        self.main_log.setMinimumHeight(120)
        logs_area.addWidget(self.main_log, 1)

        # Status bar
        self.status = QLabel("Status: Ready")
        self.status.setFont(QFont("Segoe UI", 11))
        root.addWidget(self.status)

    def _apply_style(self):
        # dark palette
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor("#111215"))
        pal.setColor(QPalette.WindowText, QColor("#eef2f3"))
        pal.setColor(QPalette.Base, QColor("#0b0c0d"))
        self.setPalette(pal)

        style = """
        QWidget { background-color: #0f1113; color: #eef2f3; font-family: "Segoe UI"; }
        QFrame#card {
            background-color: #151718;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.03);
        }
        QFrame#subcard {
            background-color: #17191a;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.02);
        }
        #dropArea {
            background-color: #121314;
            border-radius: 10px;
            border: 2px dashed rgba(255,255,255,0.04);
        }
        QPushButton {
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #3dbb86, stop:1 #2e8b57);
            color: white;
            border-radius: 10px;
            font-size: 14px;
            padding: 8px 12px;
        }
        QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #4fd099, stop:1 #3aa06a); }
        QTextEdit {
            background-color: #0b0c0d;
            color: #cfead6;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.03);
            font-family: "Courier New", monospace;
            font-size: 12px;
            padding: 8px;
        }
        QListWidget {
            background-color: #0b0c0d;
            border-radius: 6px;
            color: #ffffff;
            border: 1px solid rgba(255,255,255,0.03);
            padding: 6px;
        }
        QLabel { color: #eef2f3; }
        """
        self.setStyleSheet(style)

        # make clear button softer look
        self.btn_clear.setStyleSheet("""
            background: rgba(255,255,255,0.02);
            color: #d7d7d7;
            border-radius: 10px;
            font-size: 15px;
            padding: 10px;
        """)

    # ---- logging helpers ----
    def _log(self, msg, small=False):
        ts = datetime.now().strftime("%H:%M:%S")
        s = f"[{ts}] {msg}"
        if small:
            self.small_log.append(s)
        else:
            self.main_log.append(s)
        self.status.setText(f"Status: {msg}")

    # ---- sku indicator refresh (shows short icon-like text) ----
    def _refresh_sku_indicator(self):
        ok = os.path.exists(self.sku_path)
        if ok:
            self.lbl_sku_status.setText("✅  SKU Mapping")
        else:
            self.lbl_sku_status.setText("⚠️  SKU Mapping missing")

    # ---- file operations ----
    def add_files(self, paths):
        added = 0
        for p in paths:
            if p.lower().endswith(".pdf") and p not in self.selected_files:
                self.selected_files.append(p)
                self.file_list.addItem(QListWidgetItem(os.path.basename(p)))
                added += 1
        if added:
            self._log(f"Selected {len(self.selected_files)} files.", small=False)

    def on_upload_clicked(self):
        start = os.path.expanduser("~/Downloads")
        files, _ = QFileDialog.getOpenFileNames(self, "Select PDF files", start, "PDF Files (*.pdf)")
        if files:
            self.add_files(files)

    def on_clear(self):
        self.selected_files = []
        self.file_list.clear()
        self._log("Cleared selected files.", small=True)
        self.status.setText("Status: Ready")

    def on_select_sku(self):
        start = os.path.expanduser("~/Downloads")
        file, _ = QFileDialog.getOpenFileName(self, "Select SKU mapping CSV", start, "CSV Files (*.csv)")
        if file:
            self.sku_path = file
            self._log("SKU mapping file changed.", small=True)
            self._refresh_sku_indicator()

    def on_open_output(self):
        out = os.path.expanduser("~/Downloads/output")
        os.makedirs(out, exist_ok=True)
        try:
            subprocess.Popen(["xdg-open", out])
        except Exception:
            QMessageBox.information(self, "Output Folder", f"Open folder: {out}")

    # ---- generate action ----
    def on_generate(self):
        if not self.selected_files:
            QMessageBox.warning(self, "No Files", "Please upload at least one PDF file.")
            return

        # disable UI while running
        self._set_ui_enabled(False)
        self._log("Starting processing...", small=False)

        # worker/thread
        worker = Worker(self.selected_files, self.sku_path)
        thread = QThread()
        worker.moveToThread(thread)

        worker.log.connect(lambda m: self._log(m, small=False))
        worker.finished.connect(self._on_finished)
        worker.error.connect(self._on_error)
        thread.started.connect(worker.run)

        # cleanup
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        thread.start()

    def _on_finished(self, final_path):
        self._log(f"Completed: {final_path}", small=False)
        QMessageBox.information(self, "Done", f"Processing complete.\n{final_path}")
        self._set_ui_enabled(True)

    def _on_error(self, err):
        self._log(f"Error: {err}", small=False)
        QMessageBox.critical(self, "Processing Error", str(err))
        self._set_ui_enabled(True)

    def _set_ui_enabled(self, yes: bool):
        for w in (self.btn_generate, self.btn_select_sku, self.btn_open_output,
                  self.btn_clear, self.btn_upload):
            w.setEnabled(yes)


# -----------------------
# run
# -----------------------
def main():
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    w = LabelApp()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
