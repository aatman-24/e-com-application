# #!/usr/bin/env python3
# import sys
# import os
# import subprocess
# from datetime import datetime
# from pathlib import Path

# from PyQt5.QtWidgets import (
#     QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
#     QFileDialog, QListWidget, QMessageBox, QTextEdit, QProgressBar,
#     QSpacerItem, QSizePolicy
# )
# from PyQt5.QtCore import Qt, QThread, pyqtSignal

# # Import your business logic
# from label_processor import merge_input_pdfs, sort_pdf_by_parent_sku, crop_and_fit_labels


# class Worker(QThread):
#     log = pyqtSignal(str)
#     finished_success = pyqtSignal(str)
#     finished_error = pyqtSignal(str)

#     def __init__(self, input_files, sku_mapping_csv, output_dir):
#         super().__init__()
#         self.input_files = input_files[:]
#         self.sku_mapping_csv = sku_mapping_csv
#         self.output_dir = Path(output_dir)

#     def run(self):
#         try:
#             now = datetime.now()
#             date_str = now.strftime("%d-%b-%Y").lower()
#             hour_str = now.strftime("%H%M%S")

#             merged_pdf = str(self.output_dir / f"{date_str}_merged_{hour_str}.pdf")
#             self.log.emit("Merging input files...")
#             merge_input_pdfs(self.input_files, merged_pdf)

#             temp_sorted_pdf = str(self.output_dir / f"{date_str}_sorted_{hour_str}.pdf")
#             self.log.emit("Sorting pages by SKU...")
#             sort_pdf_by_parent_sku(merged_pdf, self.sku_mapping_csv, temp_sorted_pdf)

#             final_output_pdf = str(self.output_dir / f"{date_str}_label_{hour_str}.pdf")
#             self.log.emit("Cropping and fitting labels...")
#             crop_and_fit_labels(temp_sorted_pdf, final_output_pdf)

#             # Cleanup
#             for temp in [merged_pdf, temp_sorted_pdf]:
#                 try:
#                     os.remove(temp)
#                 except Exception:
#                     pass

#             self.finished_success.emit(final_output_pdf)
#         except Exception as e:
#             self.finished_error.emit(str(e))


# class LabelAppDark(QWidget):
#     def __init__(self):
#         super().__init__()
#         self.setWindowTitle("🩶 Label Generator — Dark Mode")
#         self.setMinimumSize(780, 560)
#         self.selected_files = []
#         self.sku_mapping_file = os.path.expanduser("~/Documents/e-com-application/label-cropper/data/sku_mapping.csv")
#         self.output_dir = os.path.expanduser("~/Downloads/output")
#         os.makedirs(self.output_dir, exist_ok=True)

#         self.worker = None
#         self._build_ui()
#         self._apply_dark_theme()
#         self._update_sku_label()

#     def _build_ui(self):
#         layout = QVBoxLayout()
#         layout.setSpacing(15)
#         layout.setContentsMargins(20, 20, 20, 20)
#         self.setLayout(layout)

#         top = QHBoxLayout()
#         layout.addLayout(top, 3)

#         # Left side: file list
#         left = QVBoxLayout()
#         top.addLayout(left, 3)

#         left.addWidget(QLabel("📄 Selected PDF files:"))
#         self.file_list = QListWidget()
#         self.file_list.setStyleSheet("background-color: #222; color: #ccc;")
#         left.addWidget(self.file_list)

#         btn_row = QHBoxLayout()
#         left.addLayout(btn_row)

#         self.btn_upload = QPushButton("📂 Upload Files")
#         self.btn_upload.clicked.connect(self.upload_files)
#         btn_row.addWidget(self.btn_upload)

#         self.btn_clear = QPushButton("🧹 Clear")
#         self.btn_clear.clicked.connect(self.clear_files)
#         btn_row.addWidget(self.btn_clear)

#         # Right side
#         right = QVBoxLayout()
#         top.addLayout(right, 2)

#         right.addWidget(QLabel("🧾 SKU Mapping File (fixed path):"))
#         self.sku_label = QLabel("(not selected)")
#         self.sku_label.setWordWrap(True)
#         right.addWidget(self.sku_label)

#         self.btn_select_sku = QPushButton("Change SKU File (optional)")
#         self.btn_select_sku.clicked.connect(self.select_sku_mapping)
#         right.addWidget(self.btn_select_sku)

#         right.addSpacing(10)
#         self.btn_proceed = QPushButton("🚀 Generate Labels")
#         self.btn_proceed.clicked.connect(self.proceed)
#         right.addWidget(self.btn_proceed)

#         self.btn_open_output = QPushButton("📁 Open Output Folder")
#         self.btn_open_output.clicked.connect(self.open_output_folder)
#         right.addWidget(self.btn_open_output)

#         right.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

#         # Progress Bar
#         self.progress = QProgressBar()
#         self.progress.setRange(0, 0)
#         self.progress.setVisible(False)
#         layout.addWidget(self.progress)

#         # Logs
#         layout.addWidget(QLabel("📋 Logs:"))
#         self.log_area = QTextEdit()
#         self.log_area.setReadOnly(True)
#         self.log_area.setStyleSheet("background-color: #111; color: #8f8; font-family: monospace; font-size: 12px;")
#         layout.addWidget(self.log_area, 2)

#         self.status_label = QLabel("")
#         layout.addWidget(self.status_label)

#     def _apply_dark_theme(self):
#         self.setStyleSheet("""
#             QWidget {
#                 background-color: #121212;
#                 color: #ddd;
#                 font-family: 'Segoe UI', sans-serif;
#                 font-size: 13px;
#             }
#             QPushButton {
#                 background-color: #333;
#                 color: #eee;
#                 border: 1px solid #555;
#                 border-radius: 8px;
#                 padding: 8px 14px;
#                 font-size: 14px;
#             }
#             QPushButton:hover {
#                 background-color: #444;
#             }
#             QPushButton:pressed {
#                 background-color: #555;
#             }
#             QProgressBar {
#                 border: 1px solid #666;
#                 border-radius: 4px;
#                 background: #222;
#                 text-align: center;
#                 color: #fff;
#             }
#             QProgressBar::chunk {
#                 background-color: #3a8dff;
#                 width: 20px;
#             }
#             QLabel {
#                 font-weight: 500;
#             }
#         """)

#     def _update_sku_label(self):
#         if os.path.exists(self.sku_mapping_file):
#             self.sku_label.setText(self.sku_mapping_file)
#         else:
#             self.sku_label.setText("(SKU mapping not found)")

#     def upload_files(self):
#         files, _ = QFileDialog.getOpenFileNames(
#             self, "Select PDF Files", os.path.expanduser("~/Downloads"), "PDF Files (*.pdf)"
#         )
#         if files:
#             self.selected_files = files
#             self.file_list.clear()
#             self.file_list.addItems(files)
#             self.log(f"Selected {len(files)} files.")

#     def select_sku_mapping(self):
#         file, _ = QFileDialog.getOpenFileName(self, "Select SKU Mapping CSV", "", "CSV Files (*.csv)")
#         if file:
#             self.sku_mapping_file = file
#             self._update_sku_label()
#             self.log(f"SKU mapping set to: {file}")

#     def clear_files(self):
#         self.selected_files = []
#         self.file_list.clear()
#         self.log("Cleared selected files.")

#     def open_output_folder(self):
#         subprocess.Popen(["xdg-open", self.output_dir])

#     def log(self, msg):
#         ts = datetime.now().strftime("%H:%M:%S")
#         self.log_area.append(f"[{ts}] {msg}")

#     def proceed(self):
#         if not self.selected_files:
#             QMessageBox.warning(self, "No Files", "Please upload at least one PDF.")
#             return
#         if not os.path.exists(self.sku_mapping_file):
#             QMessageBox.warning(self, "Missing SKU File", "Default SKU mapping not found.")
#             return

#         self._set_ui_enabled(False)
#         self.progress.setVisible(True)
#         self.log("Processing started...")

#         self.worker = Worker(self.selected_files, self.sku_mapping_file, self.output_dir)
#         self.worker.log.connect(self.log)
#         self.worker.finished_success.connect(self._on_success)
#         self.worker.finished_error.connect(self._on_error)
#         self.worker.start()

#     def _set_ui_enabled(self, enabled):
#         for btn in [self.btn_upload, self.btn_clear, self.btn_select_sku, self.btn_proceed, self.btn_open_output]:
#             btn.setEnabled(enabled)

#     def _on_success(self, final_path):
#         self.progress.setVisible(False)
#         self._set_ui_enabled(True)
#         self.log(f"✅ Done! File saved at: {final_path}")
#         QMessageBox.information(self, "Success", f"Output generated:\n{final_path}")

#     def _on_error(self, err):
#         self.progress.setVisible(False)
#         self._set_ui_enabled(True)
#         self.log(f"❌ Error: {err}")
#         QMessageBox.critical(self, "Error", err)


# def main():
#     app = QApplication(sys.argv)
#     win = LabelAppDark()
#     win.show()
#     sys.exit(app.exec_())


# if __name__ == "__main__":
#     main()


#!/usr/bin/env python3
import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QListWidget, QMessageBox, QTextEdit, QProgressBar,
    QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

# Import logic
from label_processor import merge_input_pdfs, sort_pdf_by_parent_sku, crop_and_fit_labels


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

            merged_pdf = str(self.output_dir / f"{date_str}_merged_{hour_str}.pdf")
            self.log.emit("Merging input files...")
            merge_input_pdfs(self.input_files, merged_pdf)

            temp_sorted_pdf = str(self.output_dir / f"{date_str}_sorted_{hour_str}.pdf")
            self.log.emit("Sorting pages by SKU...")
            sort_pdf_by_parent_sku(merged_pdf, self.sku_mapping_csv, temp_sorted_pdf)

            final_output_pdf = str(self.output_dir / f"{date_str}_label_{hour_str}.pdf")
            self.log.emit("Cropping and fitting labels...")
            crop_and_fit_labels(temp_sorted_pdf, final_output_pdf)

            # Cleanup
            for temp in [merged_pdf, temp_sorted_pdf]:
                try:
                    os.remove(temp)
                except Exception:
                    pass

            self.finished_success.emit(final_output_pdf)
        except Exception as e:
            self.finished_error.emit(str(e))


class LabelAppDark(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🩶 Label Generator — Dark Mode")
        self.setMinimumSize(820, 600)
        self.selected_files = []
        self.sku_mapping_file = os.path.expanduser("~/Documents/e-com-application/label-cropper/data/sku_mapping.csv")
        self.output_dir = os.path.expanduser("~/Downloads/output")
        os.makedirs(self.output_dir, exist_ok=True)

        self.worker = None
        self._build_ui()
        self._apply_dark_theme()
        self._update_sku_label()

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)
        self.setLayout(layout)

        # Title
        title = QLabel("🩶 Label Generator — Dark Edition")
        title_font = QFont("Segoe UI", 16, QFont.Bold)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        top = QHBoxLayout()
        layout.addLayout(top, 3)

        # Left: file list
        left = QVBoxLayout()
        top.addLayout(left, 3)

        label_files = QLabel("📄 Selected PDF Files:")
        label_files.setFont(QFont("Segoe UI", 12, QFont.Bold))
        left.addWidget(label_files)

        self.file_list = QListWidget()
        self.file_list.setStyleSheet("background-color: #1a1a1a; color: #ccc; border-radius: 6px;")
        left.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        left.addLayout(btn_row)

        self.btn_upload = QPushButton("📂 Upload Files")
        self.btn_upload.clicked.connect(self.upload_files)
        btn_row.addWidget(self.btn_upload)

        self.btn_clear = QPushButton("🧹 Clear")
        self.btn_clear.clicked.connect(self.clear_files)
        btn_row.addWidget(self.btn_clear)

        # Right: actions
        right = QVBoxLayout()
        top.addLayout(right, 2)

        lbl_sku = QLabel("🧾 SKU Mapping File (fixed path):")
        lbl_sku.setFont(QFont("Segoe UI", 12, QFont.Bold))
        right.addWidget(lbl_sku)

        self.sku_label = QLabel("(not selected)")
        self.sku_label.setWordWrap(True)
        right.addWidget(self.sku_label)

        self.btn_select_sku = QPushButton("Change SKU File (optional)")
        self.btn_select_sku.clicked.connect(self.select_sku_mapping)
        right.addWidget(self.btn_select_sku)

        right.addSpacing(15)
        self.btn_proceed = QPushButton("🚀 Generate Labels")
        self.btn_proceed.clicked.connect(self.proceed)
        right.addWidget(self.btn_proceed)

        self.btn_open_output = QPushButton("📁 Open Output Folder")
        self.btn_open_output.clicked.connect(self.open_output_folder)
        right.addWidget(self.btn_open_output)

        right.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Logs
        lbl_logs = QLabel("📋 Logs:")
        lbl_logs.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(lbl_logs)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background-color: #0e0e0e; color: #8f8; font-family: monospace; font-size: 13px;")
        layout.addWidget(self.log_area, 2)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
            }
            QPushButton {
                background-color: #2e2e2e;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 10px;
                padding: 10px 18px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
            QPushButton:pressed {
                background-color: #4a4a4a;
            }
            QProgressBar {
                border: 1px solid #666;
                border-radius: 6px;
                background: #222;
                text-align: center;
                color: #fff;
                font-size: 13px;
            }
            QProgressBar::chunk {
                background-color: #4a90e2;
                width: 25px;
            }
            QLabel {
                font-weight: 500;
            }
        """)

    def _update_sku_label(self):
        if os.path.exists(self.sku_mapping_file):
            self.sku_label.setText(self.sku_mapping_file)
        else:
            self.sku_label.setText("(SKU mapping not found)")

    def upload_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", os.path.expanduser("~/Downloads"), "PDF Files (*.pdf)"
        )
        if files:
            self.selected_files = files
            self.file_list.clear()
            self.file_list.addItems(files)
            self.log(f"Selected {len(files)} files.")

    def select_sku_mapping(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select SKU Mapping CSV", "", "CSV Files (*.csv)")
        if file:
            self.sku_mapping_file = file
            self._update_sku_label()
            self.log(f"SKU mapping set to: {file}")

    def clear_files(self):
        self.selected_files = []
        self.file_list.clear()
        self.log("Cleared selected files.")

    def open_output_folder(self):
        subprocess.Popen(["xdg-open", self.output_dir])

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{ts}] {msg}")

    def proceed(self):
        if not self.selected_files:
            QMessageBox.warning(self, "No Files", "Please upload at least one PDF.")
            return
        if not os.path.exists(self.sku_mapping_file):
            QMessageBox.warning(self, "Missing SKU File", "Default SKU mapping not found.")
            return

        self._set_ui_enabled(False)
        self.progress.setVisible(True)
        self.log("Processing started...")

        self.worker = Worker(self.selected_files, self.sku_mapping_file, self.output_dir)
        self.worker.log.connect(self.log)
        self.worker.finished_success.connect(self._on_success)
        self.worker.finished_error.connect(self._on_error)
        self.worker.start()

    def _set_ui_enabled(self, enabled):
        for btn in [self.btn_upload, self.btn_clear, self.btn_select_sku, self.btn_proceed, self.btn_open_output]:
            btn.setEnabled(enabled)

    def _on_success(self, final_path):
        self.progress.setVisible(False)
        self._set_ui_enabled(True)
        self.log(f"✅ Done! File saved at: {final_path}")
        QMessageBox.information(self, "Success", f"Output generated:\n{final_path}")

    def _on_error(self, err):
        self.progress.setVisible(False)
        self._set_ui_enabled(True)
        self.log(f"❌ Error: {err}")
        QMessageBox.critical(self, "Error", err)


def main():
    app = QApplication(sys.argv)
    win = LabelAppDark()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
