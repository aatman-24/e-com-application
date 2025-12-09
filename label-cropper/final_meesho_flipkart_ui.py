#!/usr/bin/env python3
import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path
from threading import Thread

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QListWidget, QTextEdit, QSizePolicy, QSpacerItem, QMessageBox, QRadioButton, QGroupBox, QFrame
)
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QObject

# Import existing label processor logic (unchanged)
from final_meesho_flipkart_service import (
    merge_input_pdfs,
    sort_pdf_by_parent_sku,
    crop_and_fit_labels,
    append_summary_page,
    process_flipkart_labels,
    crop_flipkart_labels
)


# ------------------------------
# Background Worker
# ------------------------------
# class Worker(QObject):
#     log = pyqtSignal(str)
#     finished = pyqtSignal(str)    # final output path
#     error = pyqtSignal(str)

#     def __init__(self, files, sku_csv, mode="meesho"):
#         super().__init__()
#         self.files = list(files)
#         self.sku_csv = sku_csv
#         self.mode = mode  # "meesho" or "flipkart"

#     def run(self):
#         try:
#             now = datetime.now()
#             date_str = now.strftime("%d-%b-%Y").lower()
#             hour_str = now.strftime("%H%M%S")

#             out_dir = Path.home() / "Downloads" / "output"
#             out_dir.mkdir(parents=True, exist_ok=True)

#             if self.mode == "flipkart":
#                 # ---------- Flipkart pipeline ----------
#                 self.log.emit(f"[Flipkart] Merging {len(self.files)} file(s)...")
#                 final_pdf = process_flipkart_labels(self.files, str(out_dir))
#                 self.log.emit("[Flipkart] Completed.")
#                 self.finished.emit(final_pdf)

#             else:
#                 # ---------- Meesho pipeline (existing) ----------
#                 merged = str(out_dir / f"{date_str}_merged_{hour_str}.pdf")
#                 sorted_pdf = str(out_dir / f"{date_str}_sorted_{hour_str}.pdf")
#                 final_pdf = str(out_dir / f"{date_str}_label_{hour_str}.pdf")

#                 self.log.emit(f"[Meesho] Step 1 — merging {len(self.files)} file(s)...")
#                 merge_input_pdfs(self.files, merged)

#                 if self.sku_csv and os.path.exists(self.sku_csv):
#                     self.log.emit("[Meesho] Step 2 — sorting by SKU mapping...")
#                     sort_pdf_by_parent_sku(merged, self.sku_csv, sorted_pdf)
#                     crop_input = sorted_pdf
#                 else:
#                     self.log.emit("[Meesho] Step 2 — SKU mapping missing; skipping sort.")
#                     crop_input = merged

#                 self.log.emit("[Meesho] Step 3 — cropping & fitting labels (100×100 mm)...")
#                 crop_and_fit_labels(crop_input, final_pdf)

#                 # (optional) summary page if you use it
#                 try:
#                     self.log.emit("[Meesho] Step 4 — appending summary page...")
#                     append_summary_page(final_pdf)
#                 except Exception as e:
#                     self.log.emit(f"[Meesho] Summary failed: {e}")

#                 # remove temp files if present
#                 for tmp in (merged, sorted_pdf):
#                     try:
#                         if os.path.exists(tmp) and tmp != final_pdf:
#                             os.remove(tmp)
#                     except Exception:
#                         pass

#                 self.log.emit("Completed.")
#                 self.finished.emit(final_pdf)

#         except Exception as e:
#             self.error.emit(str(e))



class Worker(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, files, sku_mapping_file, platform="meesho"):
        super().__init__()
        self.files = list(files)
        self.sku_mapping_file = sku_mapping_file
        self.platform = platform   # "meesho" or "flipkart"

    def run(self):
        try:
            now = datetime.now()
            date_str = now.strftime("%d-%b-%Y").lower()
            hour_str = now.strftime("%H%M%S")

            out_dir = Path.home() / "Downloads" / "output"
            out_dir.mkdir(parents=True, exist_ok=True)

            if self.platform == "meesho":
                # old Meesho flow
                merged = str(out_dir / f"{date_str}_merged_{hour_str}.pdf")
                sorted_pdf = str(out_dir / f"{date_str}_sorted_{hour_str}.pdf")
                final_pdf = str(out_dir / f"{date_str}_label_{hour_str}.pdf")

                self.log.emit(f"Step 1 — merging {len(self.files)} file(s)...")
                merge_input_pdfs(self.files, merged)

                self.log.emit("Step 2 — sorting by SKU mapping...")
                sort_pdf_by_parent_sku(merged, self.sku_mapping_file, sorted_pdf)

                self.log.emit("Step 3 — cropping & fitting labels (100×100 mm)...")
                crop_and_fit_labels(sorted_pdf, final_pdf)

                self.log.emit("Step 4 — appending summary page...")
                append_summary_page(final_pdf)

            else:
                # Flipkart flow: no merge/sort/summary, just crop invoice off and fit
                final_pdf = str(out_dir / f"{date_str}_flipkart_{hour_str}.pdf")
                self.log.emit(f"Flipkart: cropping {len(self.files)} file(s)...")

                # if your cropper expects one file at a time, loop:
                for src_path in self.files:
                    # e.g. crop_flipkart_labels(src_path, final_pdf) OR
                    # build separate name per input – adjust to your function
                    crop_flipkart_labels(src_path, final_pdf)

            self.log.emit("Completed.")
            self.finished.emit(final_pdf)

        except Exception as e:
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

        # NEW: default platform
        self.platform = "meesho"        # or "flipkart"

        self._build_ui()
        self.apply_dark_theme()
        self._update_sku_label()


    def proceed(self):
        
        if not self.selected_files:
            QMessageBox.warning(self, "No Files", "Please upload at least one PDF file.")
            return

        # platform is kept in self.platform by the radio buttons
        platform = self.platform       # "meesho" or "flipkart"

        self.log(f"🚀 Starting label generation ({platform})...")
        self.status_label.setText("Processing...")
        self._set_ui_enabled(False)

        worker = Worker(self.selected_files, self.sku_mapping_file, platform)
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

        # SKU mapping (used only for Meesho)
        lbl_mapping = QLabel("SKU Mapping (Meesho):")
        lbl_mapping.setFont(QFont("Arial", 13, QFont.Bold))
        right_layout.addWidget(lbl_mapping)

        self.mapping_label = QLabel()
        self.mapping_label.setWordWrap(True)
        right_layout.addWidget(self.mapping_label)

        self.btn_select_sku = QPushButton("🧾 Select SKU Mapping File")
        self.btn_select_sku.clicked.connect(self.select_sku_mapping)
        right_layout.addWidget(self.btn_select_sku)

        # --- NEW: platform selector (Meesho vs Flipkart) ---
        # platform_box = QGroupBox("Platform")
        # platform_layout = QVBoxLayout(platform_box)

        # self.rb_meesho = QRadioButton("Meesho (merge + sort + crop + summary)")
        # self.rb_flipkart = QRadioButton("Flipkart (crop label only)")
        # self.rb_meesho.setChecked(True)  # default

        # when user changes, remember current platform
        # self.rb_meesho.toggled.connect(
        #     lambda checked: setattr(self, "platform", "meesho" if checked else "flipkart")
        # )

        # platform_layout.addWidget(self.rb_meesho)
        # platform_layout.addWidget(self.rb_flipkart)
        # right_layout.addWidget(platform_box)


        # --- Platform selector (clean & big) ---
        # platform_box = QFrame()
        # platform_box.setObjectName("platformBox")
        # platform_layout = QHBoxLayout(platform_box)
        # platform_layout.setSpacing(30)

        # self.rb_meesho = QRadioButton("Meesho")
        # self.rb_flipkart = QRadioButton("Flipkart")

        # self.rb_meesho.setChecked(True)

        # platform_layout.addWidget(self.rb_meesho)
        # platform_layout.addWidget(self.rb_flipkart)

        # right_layout.addWidget(QLabel("Platform:"))
        # right_layout.addWidget(platform_box)

        # # track selection
        # self.rb_meesho.toggled.connect(
        #     lambda checked: setattr(self, "platform", "meesho" if checked else "flipkart")
        # )


        # --- Platform selection (Meesho / Flipkart) ---
        mode_label = QLabel("Platform:")
        mode_label.setFont(QFont("Arial", 12, QFont.Bold))
        right_layout.addWidget(mode_label)

        mode_row = QHBoxLayout()
        self.radio_meesho = QRadioButton("Meesho")
        self.radio_flipkart = QRadioButton("Flipkart")

        # default selection
        self.radio_meesho.setChecked(True)

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

        for rb in [getattr(self, "radio_meesho", None), getattr(self, "radio_flipkart", None)]:
            if rb is not None:
                rb.setStyleSheet(radio_style)

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
