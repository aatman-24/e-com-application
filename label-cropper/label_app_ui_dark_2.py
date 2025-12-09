#!/usr/bin/env python3
import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path
from threading import Thread

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QListWidget, QTextEdit, QSizePolicy, QSpacerItem, QMessageBox
)
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QObject

# Import existing label processor logic (unchanged)
from label_processor_3 import (
    merge_input_pdfs,
    sort_pdf_by_parent_sku,
    crop_and_fit_labels,
    append_summary_page
)


# ------------------------------
# Background Worker
# ------------------------------
class Worker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, input_files, sku_mapping_csv):
        super().__init__()
        self.input_files = input_files
        self.sku_mapping_csv = sku_mapping_csv

    def run(self):
        try:
            now = datetime.now()
            date_str = now.strftime("%d-%b-%Y").lower()
            hour_str = now.strftime("%H%M%S")

            output_dir = Path.home() / "Downloads" / "output"
            output_dir.mkdir(parents=True, exist_ok=True)

            merged_pdf = str(output_dir / f"{date_str}_merged_{hour_str}.pdf")
            sorted_pdf = str(output_dir / f"{date_str}_sorted_{hour_str}.pdf")
            final_pdf = str(output_dir / f"{date_str}_label_{hour_str}.pdf")

            self.log.emit("🌀 Step 1: Merging input PDFs...")
            merge_input_pdfs(self.input_files, merged_pdf)

            if self.sku_mapping_csv and os.path.exists(self.sku_mapping_csv):
                self.log.emit("🔢 Step 2: Sorting by SKU mapping...")
                sort_pdf_by_parent_sku(merged_pdf, self.sku_mapping_csv, sorted_pdf)
                temp_input = sorted_pdf
            else:
                self.log.emit("⚠️ SKU mapping not found. Skipping sort.")
                temp_input = merged_pdf

            self.log.emit("✂️ Step 3: Cropping and fitting labels...")
            crop_and_fit_labels(temp_input, final_pdf)


            # NEW: Step 4 — create summary
            self.log.emit("Step 4 — generating summary page...")
            append_summary_page(final_pdf)

            final_result = final_pdf  # if summary fails, fall back

            # remove temp files if present
            for tmp in (merged_pdf, sorted_pdf):
                try:
                    if os.path.exists(tmp) and tmp != final_result:
                        os.remove(tmp)
                except Exception:
                    pass

            self.log.emit(f"Final Output: {final_pdf}")
            self.finished.emit(final_pdf)
        except Exception as e:
            print(e)
            self.error.emit(str(e))


# ------------------------------
# Main Dark UI Application
# ------------------------------
class LabelApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Label Generator")
        self.setMinimumSize(900, 600)
        self.setWindowIcon(QIcon.fromTheme("document-new"))

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.sku_mapping_file = os.path.join(base_dir, "data", "sku_mapping.csv")
        self.selected_files = []

        self._build_ui()
        self.apply_dark_theme()
        self._update_sku_label()

    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        self.setLayout(main_layout)

        # Title
        title = QLabel("Label Generator")
        title.setFont(QFont("Arial", 22, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Top Layout (Files + Mapping)
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        # Left Panel — File selection
        left_layout = QVBoxLayout()
        lbl_files = QLabel("Selected PDF Files:")
        lbl_files.setFont(QFont("Arial", 13, QFont.Bold))
        left_layout.addWidget(lbl_files)

        self.file_list = QListWidget()
        left_layout.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        self.btn_upload = QPushButton("📂 Upload Files")
        self.btn_upload.clicked.connect(self.upload_files)
        btn_row.addWidget(self.btn_upload)

        self.btn_clear = QPushButton("🧹 Clear")
        self.btn_clear.clicked.connect(self.clear_files)
        btn_row.addWidget(self.btn_clear)
        left_layout.addLayout(btn_row)

        top_layout.addLayout(left_layout, 2)

        # Right Panel — SKU mapping + Actions
        right_layout = QVBoxLayout()
        lbl_mapping = QLabel("SKU Mapping:")
        lbl_mapping.setFont(QFont("Arial", 13, QFont.Bold))
        right_layout.addWidget(lbl_mapping)

        self.mapping_label = QLabel()
        self.mapping_label.setWordWrap(True)
        right_layout.addWidget(self.mapping_label)

        # Add button to override mapping file
        self.btn_select_sku = QPushButton("🧾 Select SKU Mapping File")
        self.btn_select_sku.clicked.connect(self.select_sku_mapping)
        right_layout.addWidget(self.btn_select_sku)

        self.btn_proceed = QPushButton("🚀 Generate Labels")
        self.btn_proceed.clicked.connect(self.proceed)
        right_layout.addWidget(self.btn_proceed)

        self.btn_open_output = QPushButton("📁 Open Output Folder")
        self.btn_open_output.clicked.connect(self.open_output_folder)
        right_layout.addWidget(self.btn_open_output)

        right_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        top_layout.addLayout(right_layout, 1)

        # Logs section
        lbl_logs = QLabel("Logs:")
        lbl_logs.setFont(QFont("Arial", 13, QFont.Bold))
        main_layout.addWidget(lbl_logs)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        main_layout.addWidget(self.log_area, 2)

        # Status label
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)

    def _update_sku_label(self):
        if os.path.exists(self.sku_mapping_file):
            self.mapping_label.setText("✅ Default mapping loaded")
        else:
            self.mapping_label.setText("⚠️ Mapping file not found")

    def apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(40, 40, 40))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(70, 70, 70))
        palette.setColor(QPalette.ButtonText, Qt.white)
        self.setPalette(palette)

        button_style = """
        QPushButton {
            background-color: #2e8b57;
            color: white;
            border-radius: 10px;
            padding: 12px 24px;
            font-size: 15px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #3cb371;
        }
        """
        for btn in [
            self.btn_upload, self.btn_clear,
            self.btn_select_sku, self.btn_proceed, self.btn_open_output
        ]:
            btn.setStyleSheet(button_style)

    def log(self, message):
        self.log_area.append(message)
        self.log_area.ensureCursorVisible()

    def upload_files(self):
        downloads = os.path.expanduser("~/Downloads")
        files, _ = QFileDialog.getOpenFileNames(self, "Select PDF Files", downloads, "PDF Files (*.pdf)")
        if files:
            self.selected_files = files
            self.file_list.clear()
            for f in files:
                self.file_list.addItem(os.path.basename(f))
            self.log(f"🗂️ Selected {len(files)} file(s).")

    def clear_files(self):
        self.selected_files = []
        self.file_list.clear()
        self.log("🧹 Cleared file selection.")

    def select_sku_mapping(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select SKU Mapping File", "", "CSV Files (*.csv)")
        if file:
            self.sku_mapping_file = file
            self._update_sku_label()
            self.log(f"✅ SKU mapping file changed: {file}")

    def open_output_folder(self):
        output_path = os.path.expanduser("~/Downloads/output")
        os.makedirs(output_path, exist_ok=True)
        subprocess.Popen(["xdg-open", output_path])

    def proceed(self):
        if not self.selected_files:
            QMessageBox.warning(self, "No Files", "Please upload at least one PDF file.")
            return

        self.log("🚀 Starting label generation...")
        self.status_label.setText("Processing...")
        self._set_ui_enabled(False)

        worker = Worker(self.selected_files, self.sku_mapping_file)
        thread = Thread(target=worker.run, daemon=True)
        worker.log.connect(self.log)
        worker.finished.connect(self.on_success)
        worker.error.connect(self.on_error)
        thread.start()

    def on_success(self, final_path):
        self.status_label.setText("✅ Completed Successfully.")
        self.log(f"🎯 Final Output: {final_path}")
        self._set_ui_enabled(True)
        QMessageBox.information(self, "Success", f"Processing completed!\nFile: {final_path}")

    def on_error(self, error):
        self.status_label.setText("❌ Error Occurred.")
        self.log(f"Error: {error}")
        self._set_ui_enabled(True)
        QMessageBox.critical(self, "Error", str(error))

    def _set_ui_enabled(self, enabled):
        for btn in [
            self.btn_upload, self.btn_clear,
            self.btn_select_sku, self.btn_proceed, self.btn_open_output
        ]:
            btn.setEnabled(enabled)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LabelApp()
    window.show()
    sys.exit(app.exec_())
