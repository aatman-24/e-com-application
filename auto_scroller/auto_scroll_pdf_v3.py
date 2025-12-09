#!/usr/bin/env python3
import sys
import os
import json
import hashlib
import hmac

import fitz  # PyMuPDF
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QMainWindow,
    QPushButton,
    QHBoxLayout,
    QSpinBox,
    QFileDialog,
    QLineEdit,
    QDialog,
    QFormLayout,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage

# ==========================
#  LICENSE CONFIG
# ==========================

# ⚠️ CHANGE THIS BEFORE SELLING ⚠️
SECRET_KEY = "aatman.code@gmail.com"

# Where we store license info on the user machine
APP_NAME = "pdf_autoscroller"
LICENSE_FILENAME = "license.json"


def get_license_file_path():
    """Return a path like: ~/.pdf_autoscroller/license.json (works on Windows/Linux)."""
    home = os.path.expanduser("~")
    app_dir = os.path.join(home, f".{APP_NAME}")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, LICENSE_FILENAME)


def calc_license_key(name: str, email: str) -> str:
    """
    Generate license key from name + email + SECRET_KEY.
    This must match the generator script you use.
    """
    text = f"{name.strip()}|{email.strip()}|{SECRET_KEY}"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
    # Cut it down to something shorter / user-friendly
    # Example: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX (24 hex chars split)
    short = digest[:24]
    blocks = [short[i : i + 4] for i in range(0, len(short), 4)]
    return "-".join(blocks)


def verify_license(name: str, email: str, key: str) -> bool:
    """Check if the entered key matches the expected key."""
    expected = calc_license_key(name, email)
    normalized_key = key.replace(" ", "").upper()
    normalized_expected = expected.replace(" ", "").upper()
    return hmac.compare_digest(normalized_key, normalized_expected)


# ==========================
#  LICENSE DIALOG
# ==========================


class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("License Activation")

        self.name_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.key_edit = QLineEdit()

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Email:", self.email_edit)
        form.addRow("License Key:", self.key_edit)

        btn_row = QHBoxLayout()
        self.activate_btn = QPushButton("Activate")
        self.cancel_btn = QPushButton("Exit")
        btn_row.addWidget(self.activate_btn)
        btn_row.addWidget(self.cancel_btn)

        form.addRow(btn_row)
        self.setLayout(form)

        self.activate_btn.clicked.connect(self.on_activate)
        self.cancel_btn.clicked.connect(self.reject)

    def on_activate(self):
        name = self.name_edit.text().strip()
        email = self.email_edit.text().strip()
        key = self.key_edit.text().strip()

        if not name or not email or not key:
            QMessageBox.warning(self, "Missing info", "Please fill all fields.")
            return

        if verify_license(name, email, key):
            # Save license for next time
            license_file = get_license_file_path()
            data = {"name": name, "email": email, "key": key}
            with open(license_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

            QMessageBox.information(self, "Success", "License activated successfully.")
            self.accept()
        else:
            QMessageBox.critical(self, "Invalid license", "The license key is not valid.")


def ensure_license(app):
    """
    Check if a valid license exists.
    If not, show dialog.
    If still invalid (user cancels or fails) -> exit program.
    """
    license_file = get_license_file_path()

    # 1) Try to load existing license
    if os.path.exists(license_file):
        try:
            with open(license_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("name", "")
            email = data.get("email", "")
            key = data.get("key", "")

            if verify_license(name, email, key):
                return True  # OK, continue
        except Exception:
            pass  # any error -> treat as no valid license

    # 2) If we reach here, show dialog
    dlg = LicenseDialog()
    result = dlg.exec_()
    if result == QDialog.Accepted:
        # dialog already saved license & checked validity
        return True

    # User cancelled or closed -> exit
    QMessageBox.critical(None, "License required", "A valid license is required to use this software.")
    app.quit()
    return False


# ==========================
#  MAIN APP WINDOW
# ==========================


class PdfAutoScrollViewer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Auto Scrolling PDF Viewer")
        self.resize(1000, 750)

        # ===== Central layout =====
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ===== Top controls row =====
        controls_layout = QHBoxLayout()
        main_layout.addLayout(controls_layout)

        # Open PDF button
        self.open_btn = QPushButton("Open PDF")
        self.open_btn.clicked.connect(self.choose_file)
        controls_layout.addWidget(self.open_btn)

        # Readonly field to show selected file
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        controls_layout.addWidget(self.file_path_edit, 1)  # stretch = 1

        # Interval input
        controls_layout.addWidget(QLabel("Interval (ms):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(10, 5000)
        self.interval_spin.setValue(50)  # default
        controls_layout.addWidget(self.interval_spin)

        # Step input
        controls_layout.addWidget(QLabel("Step (px):"))
        self.step_spin = QSpinBox()
        self.step_spin.setRange(1, 100)
        self.step_spin.setValue(2)  # default
        controls_layout.addWidget(self.step_spin)

        # Play button
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.start_scrolling)
        controls_layout.addWidget(self.play_btn)

        # Stop button
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_scrolling)
        controls_layout.addWidget(self.stop_btn)

        # ===== Scroll area for PDF pages =====
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area)

        # Container inside scroll area
        self.container = QWidget()
        self.v_layout = QVBoxLayout(self.container)
        self.v_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.container)

        # Timer for auto scroll
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.auto_scroll)
        self.scroll_step = 2  # will be updated from UI

        self.current_pdf_path = None

    # ---------- UI actions ----------

    def choose_file(self):
        """Open file dialog to select PDF and then load it."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF file",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )

        if not file_path:
            return

        self.current_pdf_path = file_path
        self.file_path_edit.setText(file_path)

        self.load_pdf(file_path)

    def load_pdf(self, pdf_path):
        """Render all pages of the PDF into the scroll area."""
        # Clear previous content
        while self.v_layout.count():
            item = self.v_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        doc = fitz.open(pdf_path)

        for page in doc:
            # Zoom for better quality
            matrix = fitz.Matrix(1.5, 1.5)
            pix = page.get_pixmap(matrix=matrix)

            # Convert to QImage
            if pix.alpha:  # RGBA
                qimg = QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    QImage.Format_RGBA8888,
                ).copy()
            else:  # RGB
                qimg = QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    QImage.Format_RGB888,
                ).copy()

            pixmap = QPixmap.fromImage(qimg)

            label = QLabel()
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignCenter)

            self.v_layout.addWidget(label)

        # Small spacer at bottom
        spacer = QWidget()
        spacer.setFixedHeight(20)
        self.v_layout.addWidget(spacer)

        # Scroll to top
        self.scroll_area.verticalScrollBar().setValue(0)

    def start_scrolling(self):
        """Start auto scroll using current UI values."""
        if not self.current_pdf_path:
            # No file selected; ignore
            return

        interval = self.interval_spin.value()  # ms
        step = self.step_spin.value()          # pixels

        self.scroll_step = step
        self.timer.setInterval(interval)
        self.timer.start()

    def stop_scrolling(self):
        """Stop auto scroll."""
        self.timer.stop()

    def auto_scroll(self):
        """Move scroll bar down on each timer tick."""
        bar = self.scroll_area.verticalScrollBar()
        current_value = bar.value()
        max_value = bar.maximum()

        if current_value < max_value:
            bar.setValue(current_value + self.scroll_step)
        else:
            # End of file: stop scrolling, do NOT loop
            self.timer.stop()


def main():
    app = QApplication(sys.argv)

    # 🔐 license check before showing main window
    if not ensure_license(app):
        return

    viewer = PdfAutoScrollViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
