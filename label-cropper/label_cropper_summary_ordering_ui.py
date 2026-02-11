#!/usr/bin/env python3
"""
final_meesho_flipkart_ui_test.py

PyQt UI that calls the single-pass service processor (process_labels_single_pass)
from final_meesho_flipkart_service_test.py. UI shows logs and supports Meesho/Flipkart modes.
"""

import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path
from threading import Thread

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QListWidget, QTextEdit, QSizePolicy, QSpacerItem, QMessageBox, QRadioButton
)
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QObject

# Import only the functions the UI needs from the service module.
# The service module must export process_labels_single_pass (single-pass + summary),
# merge_input_pdfs, process_flipkart_labels, and crop_flipkart_labels.
from label_cropper_summary_ordering import (
    merge_input_pdfs,
    process_flipkart_labels,
    crop_flipkart_labels,
    process_labels_single_pass,
)


class Worker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, files, platform="meesho"):
        super().__init__()
        self.files = list(files)
        self.platform = platform   # "meesho" or "flipkart"

    def run(self):
        try:
            now = datetime.now()
            date_str = now.strftime("%d-%b-%Y").lower()
            hour_str = now.strftime("%H%M%S")

            out_dir = Path.home() / "Downloads" / "output"
            out_dir.mkdir(parents=True, exist_ok=True)

            if self.platform == "meesho":
                # Single-pass Meesho pipeline (extract -> sort -> crop -> summary in one pass)
                merged = str(out_dir / f"{date_str}_merged_{hour_str}.pdf")
                final_pdf = str(out_dir / f"{date_str}_label_{hour_str}.pdf")

                self.log.emit(f"Step 1 — merging {len(self.files)} file(s) into: {merged}")
                merge_input_pdfs(self.files, merged)

                self.log.emit("Step 2 — processing (single-pass: extract, sort, crop & summary)...")
                try:
                    process_labels_single_pass(merged, final_pdf, append_summary=True)
                    self.log.emit(f"Step 3 — single-pass processing completed: {final_pdf}")
                except Exception as e:
                    self.log.emit(f"❌ Processing failed: {e}")
                    raise

                # Optional: remove merged intermediate if desired
                try:
                    if os.path.exists(merged) and merged != final_pdf:
                        os.remove(merged)
                except Exception:
                    pass

            else:
                # Flipkart flow
                final_pdf = str(out_dir / f"{date_str}_flipkart_{hour_str}.pdf")
                self.log.emit(f"Flipkart: cropping {len(self.files)} file(s)...")
                # If multiple files, merge first then crop; otherwise crop single file
                if len(self.files) > 1:
                    merged_fk = str(out_dir / f"{date_str}_flipkart_merged_{hour_str}.pdf")
                    merge_input_pdfs(self.files, merged_fk)
                    crop_flipkart_labels(merged_fk, final_pdf)
                    try:
                        os.remove(merged_fk)
                    except Exception:
                        pass
                else:
                    crop_flipkart_labels(self.files[0], final_pdf)

            self.log.emit("Completed.")
            self.finished.emit(final_pdf)

        except Exception as e:
            # ensure UI receives the error
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
        self.selected_files = []

        self.last_generated_pdf = None

        # default platform
        self.platform = "meesho"        # or "flipkart"

        self._build_ui()
        self.apply_dark_theme()


    def proceed(self):
        if not self.selected_files:
            QMessageBox.warning(self, "No Files", "Please upload at least one PDF file.")
            return

        # platform is kept in self.platform by the radio buttons
        platform = self.platform  # read current platform

        self.log(f"🚀 Starting label generation ({platform})...")
        self.status_label.setText("Processing...")
        self._set_ui_enabled(False)

        self.btn_open_pdf.setEnabled(False)
        self.last_generated_pdf = None

        worker = Worker(self.selected_files, platform)
        thread = Thread(target=worker.run, daemon=True)
        worker.log.connect(self.log)
        worker.finished.connect(self.on_success)
        worker.error.connect(self.on_error)
        thread.start()


    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        self.setLayout(main_layout)

        # Title
        title = QLabel("Label Generator")
        title.setFont(QFont("Arial", 22, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Top Layout (Files + Mapping/Actions)
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        # -------- LEFT PANEL (files) --------
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

        # -------- RIGHT PANEL (mapping + platform + actions) --------
        right_layout = QVBoxLayout()
        top_layout.addLayout(right_layout, 1)


        # --- Platform selection (Meesho / Flipkart) ---
        mode_label = QLabel("Platform:")
        mode_label.setFont(QFont("Arial", 12, QFont.Bold))
        right_layout.addWidget(mode_label)

        mode_row = QHBoxLayout()
        self.radio_meesho = QRadioButton("Meesho")
        self.radio_flipkart = QRadioButton("Flipkart")

        # default selection
        self.radio_meesho.setChecked(True)

        # connect radio toggles so self.platform reflects UI
        self.radio_meesho.toggled.connect(lambda checked: setattr(self, "platform", "meesho" if checked else self.platform))
        self.radio_flipkart.toggled.connect(lambda checked: setattr(self, "platform", "flipkart" if checked else self.platform))

        mode_row.addWidget(self.radio_meesho)
        mode_row.addWidget(self.radio_flipkart)
        mode_row.addStretch()

        right_layout.addLayout(mode_row)

        # Actions
        self.btn_proceed = QPushButton("🚀 Generate Labels")
        self.btn_proceed.clicked.connect(self.proceed)
        right_layout.addWidget(self.btn_proceed)

        self.btn_open_output = QPushButton("📁 Open Output Folder")
        self.btn_open_output.clicked.connect(self.open_output_folder)
        right_layout.addWidget(self.btn_open_output)

        self.btn_open_pdf = QPushButton("📄 Open Generated PDF")
        self.btn_open_pdf.setEnabled(False)   # disabled until success
        self.btn_open_pdf.clicked.connect(self.open_generated_pdf)
        right_layout.addWidget(self.btn_open_pdf)


        right_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Logs
        lbl_logs = QLabel("Logs:")
        lbl_logs.setFont(QFont("Arial", 13, QFont.Bold))
        main_layout.addWidget(lbl_logs)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        main_layout.addWidget(self.log_area, 2)

        # Status
        self.status_label = QLabel("")
        main_layout.addWidget(self.status_label)

    def open_generated_pdf(self):
        if not self.last_generated_pdf or not os.path.exists(self.last_generated_pdf):
            QMessageBox.warning(self, "File Missing", "Generated PDF not found.")
            return

        subprocess.Popen(["xdg-open", self.last_generated_pdf])

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

        # ===== RADIO BUTTON STYLE (RESTORED) =====
        radio_style = """
        QRadioButton {
            spacing: 8px;
            font-size: 15px;
            font-weight: bold;
            color: white;
        }
        QRadioButton::indicator {
            width: 18px;
            height: 18px;
            border-radius: 9px;
            border: 2px solid #3cb371;
            background: transparent;
            margin-right: 6px;
        }
        QRadioButton::indicator:checked {
            background-color: #3cb371;
        }
        """

        for rb in [self.radio_meesho, self.radio_flipkart]:
            rb.setStyleSheet(radio_style)

        # ===== BUTTON STYLE (RESTORED) =====
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
        QPushButton:disabled {
            background-color: #555;
            color: #aaa;
        }
        """

        for btn in [
            self.btn_upload,
            self.btn_clear,
            self.btn_proceed,
            self.btn_open_output,
            self.btn_open_pdf,
        ]:
            btn.setStyleSheet(button_style)



    def log(self, message):
        # prepend timestamp for better traceability
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{ts}] {message}")
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
        self.btn_open_pdf.setEnabled(False)
        self.last_generated_pdf = None
        self.log("🧹 Cleared file selection.")


    def open_output_folder(self):
        output_path = os.path.expanduser("~/Downloads/output")
        os.makedirs(output_path, exist_ok=True)
        subprocess.Popen(["xdg-open", output_path])


    def on_success(self, final_path):
        self.status_label.setText("✅ Completed Successfully.")
        self.log(f"🎯 Final Output: {final_path}")

        self.last_generated_pdf = final_path
        self.btn_open_pdf.setEnabled(True)

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
             self.btn_proceed, self.btn_open_output
        ]:
            btn.setEnabled(enabled)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LabelApp()
    window.show()

    sys.exit(app.exec_())
