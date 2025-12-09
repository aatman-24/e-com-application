#!/usr/bin/env python3
import sys
import json
import hmac
import hashlib
import uuid
import platform
from pathlib import Path

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
    QDialogButtonBox,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage

# ==================== LICENSE CONFIG ====================

# ⚠️ CHANGE THIS BEFORE BUILDING EXE (same string in generator)
SECRET_KEY = "CHANGE_ME_TO_SOME_RANDOM_LONG_STRING"

# Where license info will be stored per user
LICENSE_FILE = Path.home() / ".pdf_autoscroll_license.json"


def get_machine_id() -> str:
    """
    Generate a stable machine code from hostname + MAC.
    Shown to user, and also used internally for license check.
    """
    base = f"{platform.node()}-{uuid.getnode()}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
    return digest[:16].upper()


def calc_expected_license(email: str, machine_id: str) -> str:
    """
    SAME logic must be used in your offline license generator.
    email + machine_id + SECRET_KEY -> license key string.
    """
    email_norm = email.strip().lower()
    machine_norm = machine_id.strip().upper()
    raw = f"{email_norm}|{machine_norm}"

    digest = hmac.new(
        SECRET_KEY.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().upper()

    # 24 chars, grouped as XXXX-XXXX-... for readability
    short = digest[:24]
    return "-".join(short[i:i+4] for i in range(0, len(short), 4))


def normalize_license_input(key: str) -> str:
    """
    Remove spaces/hyphens, uppercase, then insert hyphens every 4 chars.
    So user can type with or without dashes.
    """
    cleaned = "".join(c for c in key if c.isalnum()).upper()
    return "-".join(cleaned[i:i+4] for i in range(0, len(cleaned), 4))


def verify_license(email: str, user_key: str) -> bool:
    """
    Check if user_key is valid for this email + this machine.
    """
    machine_id = get_machine_id()
    expected = calc_expected_license(email, machine_id)
    entered = normalize_license_input(user_key)
    return hmac.compare_digest(expected, entered)


def save_license_file(email: str, license_key: str):
    """
    Save normalized license to disk so next time user doesn't need to re-enter.
    """
    data = {
        "email": email.strip(),
        "license_key": normalize_license_input(license_key),
    }
    try:
        with open(LICENSE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print("Failed to save license:", e)


def load_license_file():
    if not LICENSE_FILE.exists():
        return None
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def is_license_valid() -> bool:
    """
    Called at app start. If license file exists and matches current machine, OK.
    """
    data = load_license_file()
    if not data:
        return False

    email = data.get("email", "")
    key = data.get("license_key", "")
    if not email or not key:
        return False

    return verify_license(email, key)


# ==================== LICENSE DIALOG ====================


class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("License Activation")
        self.setModal(True)

        layout = QFormLayout(self)

        self.email_edit = QLineEdit()
        self.machine_id_edit = QLineEdit()
        self.license_key_edit = QLineEdit()

        # Show machine code (user sends this to you)
        machine_id = get_machine_id()
        self.machine_id_edit.setText(machine_id)
        self.machine_id_edit.setReadOnly(True)

        layout.addRow("Email:", self.email_edit)
        layout.addRow("Machine Code:", self.machine_id_edit)
        layout.addRow("License Key:", self.license_key_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.on_activate)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def on_activate(self):
        email = self.email_edit.text().strip()
        license_key = self.license_key_edit.text().strip()

        if not email or not license_key:
            QMessageBox.warning(self, "Error", "Please fill in all fields.")
            return

        if verify_license(email, license_key):
            save_license_file(email, license_key)
            QMessageBox.information(self, "Success", "License activated successfully.")
            self.accept()  # <-- now main window will open
        else:
            QMessageBox.critical(self, "Invalid license", "The license key is invalid for this machine.")


# ==================== PDF AUTO-SCROLLER UI ====================


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
        controls_layout.addWidget(self.file_path_edit, 1)

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
            # Stop at end (no repeat)
            self.timer.stop()


# ==================== MAIN ====================


def main():
    app = QApplication(sys.argv)

    # 1) Check stored license
    if not is_license_valid():
        # 2) Ask user to activate
        dlg = LicenseDialog()
        result = dlg.exec_()
        if result != QDialog.Accepted:
            # User cancelled activation
            sys.exit(0)

    # 3) Start main app
    viewer = PdfAutoScrollViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
