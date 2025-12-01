#!/usr/bin/env python3
import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QListWidget, QMessageBox, QTextEdit, QProgressBar, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Import business logic
try:
    from label_processor import (
        merge_input_pdfs,
        sort_pdf_by_parent_sku,
        crop_and_fit_labels,
    )
except Exception as e:
    print("❌ Error importing label_processor.py — ensure it's in the same directory.")
    raise


class Worker(QThread):
    log = pyqtSignal(str)
    finished_success = pyqtSignal(str)
    finished_error = pyqtSignal(str)

    def __init__(self, input_files, sku_mapping_csv, output_dir):
        super().__init__()
        self.input_files = input_files[:]
        self.sku_mapping_csv = sku_mapping_csv
        self.output_dir = Path(output_dir)

    def run(self):
        try:
            now = datetime.now()
            date_str = now.strftime("%d-%b-%Y").lower()
            hour_str = now.strftime("%H%M%S")

            # Step 0 — Merge
            merged_pdf = str(self.output_dir / f"{date_str}_merged_{hour_str}.pdf")
            self.log.emit("Merging input PDFs...")
            merge_input_pdfs(self.input_files, merged_pdf)

            # Step 1 — Sort
            temp_sorted_pdf = str(self.output_dir / f"{date_str}_sorted_{hour_str}.pdf")
            self.log.emit("Sorting pages by parent SKU...")
            sort_pdf_by_parent_sku(merged_pdf, self.sku_mapping_csv, temp_sorted_pdf)

            # Step 2 — Crop & Fit
            final_output_pdf = str(self.output_dir / f"{date_str}_label_{hour_str}.pdf")
            self.log.emit("Cropping and scaling labels...")
            crop_and_fit_labels(temp_sorted_pdf, final_output_pdf)

            # Clean up temporary files
            for temp_file in [temp_sorted_pdf, merged_pdf]:
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

            self.finished_success.emit(final_output_pdf)
        except Exception as e:
            self.finished_error.emit(str(e))


class LabelApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Label Generator — Ubuntu")
        self.setMinimumSize(700, 520)
        self.selected_files = []
        self.worker = None

        # fixed SKU mapping
        self.sku_mapping_file = os.path.join(BASE_DIR, "data", "sku_mapping.csv")
        # self.sku_mapping_file = os.path.abspath("data/sku_mapping.csv")
        if not os.path.exists(self.sku_mapping_file):
            self.sku_mapping_file = ""
        
        if not os.path.exists(self.sku_mapping_file):
            QMessageBox.warning(self, "Missing SKU Mapping", f"Default SKU mapping not found:\n{self.sku_mapping_file}")

        self.output_dir = os.path.expanduser("~/Downloads/output")
        os.makedirs(self.output_dir, exist_ok=True)

        self._build_ui()
        self._update_sku_label()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- File selection area ---
        top_h = QHBoxLayout()
        layout.addLayout(top_h)

        # Left: file list
        vleft = QVBoxLayout()
        top_h.addLayout(vleft, 3)
        vleft.addWidget(QLabel("Selected PDF files:"))
        self.file_list = QListWidget()
        vleft.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        vleft.addLayout(btn_row)
        self.btn_upload = QPushButton("📂 Upload Files")
        self.btn_upload.clicked.connect(self.upload_files)
        btn_row.addWidget(self.btn_upload)
        self.btn_clear = QPushButton("🧹 Clear")
        self.btn_clear.clicked.connect(self.clear_files)
        btn_row.addWidget(self.btn_clear)

        # Right: SKU mapping + actions
        vright = QVBoxLayout()
        top_h.addLayout(vright, 2)
        vright.addWidget(QLabel("SKU Mapping (fixed path):"))
        self.sku_label = QLabel("(not selected)")
        self.sku_label.setWordWrap(True)
        vright.addWidget(self.sku_label)
        self.btn_select_sku = QPushButton("🧾 Select SKU Mapping File")
        self.btn_select_sku.clicked.connect(self.select_sku_mapping)
        vright.addWidget(self.btn_select_sku)

        vright.addSpacing(10)
        self.btn_proceed = QPushButton("🚀 Proceed")
        self.btn_proceed.clicked.connect(self.proceed)
        vright.addWidget(self.btn_proceed)

        self.btn_open_output = QPushButton("📁 Open Output Folder")
        self.btn_open_output.clicked.connect(self.open_output_folder)
        vright.addWidget(self.btn_open_output)
        vright.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # --- Progress + Logs ---
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        layout.addWidget(QLabel("Logs:"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area, 2)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def _update_sku_label(self):
        if self.sku_mapping_file and os.path.exists(self.sku_mapping_file):
            self.sku_label.setText(self.sku_mapping_file)
        elif self.sku_mapping_file:
            self.sku_label.setText(f"{self.sku_mapping_file} (not found)")
        else:
            self.sku_label.setText("(not selected)")

    def upload_files(self):
        downloads_path = os.path.join(Path.home(), "Downloads")
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF Files",
            downloads_path,
            "PDF Files (*.pdf)"
        )
        if files:
            self.selected_files = files
            self.file_list.clear()
            self.file_list.addItems(files)
            self.log(f"Selected {len(files)} file(s).")

    def select_sku_mapping(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select SKU Mapping CSV", "", "CSV Files (*.csv)")
        if file:
            self.sku_mapping_file = file
            self._update_sku_label()
            self.log(f"SKU mapping file set to: {file}")

    def clear_files(self):
        self.selected_files = []
        self.file_list.clear()
        self.log("Cleared selected files.")

    def open_output_folder(self):
        path = os.path.abspath(self.output_dir)
        os.makedirs(path, exist_ok=True)
        try:
            subprocess.Popen(["xdg-open", path])
        except Exception:
            QMessageBox.information(self, "Open Folder", f"Output folder: {path}")

    def log(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{ts}] {message}")

    def proceed(self):
        if not self.selected_files:
            QMessageBox.warning(self, "No files", "Please upload at least one PDF.")
            return
        if not self.sku_mapping_file or not os.path.exists(self.sku_mapping_file):
            reply = QMessageBox.question(
                self, "SKU mapping missing",
                "SKU mapping CSV not found. Continue anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        self._set_ui_enabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.log(f"Processing {len(self.selected_files)} file(s)...")

        self.worker = Worker(self.selected_files, self.sku_mapping_file, self.output_dir)
        self.worker.log.connect(self.log)
        self.worker.finished_success.connect(self._on_success)
        self.worker.finished_error.connect(self._on_error)
        self.worker.start()

    def _set_ui_enabled(self, enabled):
        for btn in [self.btn_upload, self.btn_select_sku, self.btn_proceed, self.btn_clear, self.btn_open_output]:
            btn.setEnabled(enabled)

    def _on_success(self, final_path):
        self.progress.setVisible(False)
        self._set_ui_enabled(True)
        self.log(f"✅ Done. Final output: {final_path}")
        self.status_label.setText("Processing complete.")
        QMessageBox.information(self, "Success", f"Output generated:\n{final_path}")

    def _on_error(self, error_msg):
        self.progress.setVisible(False)
        self._set_ui_enabled(True)
        self.log(f"❌ Error: {error_msg}")
        self.status_label.setText("Error occurred. See logs.")
        QMessageBox.critical(self, "Error", error_msg)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Label Generator")
    win = LabelApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
