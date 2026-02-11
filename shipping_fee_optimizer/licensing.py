# ==================== LICENSE CONFIG (APP-SPECIFIC) ====================
import json
import hmac
import hashlib
import uuid
import platform
from pathlib import Path
from PyQt5.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QMessageBox

# >>> CHANGE THESE FOR EACH APP <<<
APP_ID = "SHIPPING_FEE_OPTIMIZER"       # make unique per app
SECRET_KEY = "aatman.code@gmail.com"    # different random secret per app
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

LICENSE_FILE = Path.home() / f".license_{APP_ID}.json"


def get_machine_id() -> str:
    base = f"{platform.node()}-{uuid.getnode()}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
    return digest[:16].upper()   # what user sees as Machine Code


def calc_expected_license(email: str, machine_id: str) -> str:
    email_norm = email.strip().lower()
    machine_norm = machine_id.strip().upper()

    # NOTE: APP_ID is included here so keys differ per app
    raw = f"{APP_ID}|{email_norm}|{machine_norm}"

    digest = hmac.new(
        SECRET_KEY.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256
    ).hexdigest().upper()

    short = digest[:24]
    return "-".join(short[i:i+4] for i in range(0, len(short), 4))


def normalize_license_input(key: str) -> str:
    cleaned = "".join(c for c in key if c.isalnum()).upper()
    return "-".join(cleaned[i:i+4] for i in range(0, len(cleaned), 4))


def verify_license(email: str, machine_id: str, user_key: str) -> bool:
    expected = calc_expected_license(email, machine_id)
    entered = normalize_license_input(user_key)
    return hmac.compare_digest(expected, entered)


def save_license(email: str, license_key: str):
    data = {
        "email": email.strip(),
        "license_key": normalize_license_input(license_key),
    }
    try:
        with open(LICENSE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print("Failed to save license:", e)


def load_license():
    if not LICENSE_FILE.exists():
        return None
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def is_license_valid_for_this_machine() -> bool:
    data = load_license()
    if not data:
        return False
    email = data.get("email", "")
    key = data.get("license_key", "")
    if not email or not key:
        return False
    machine_id = get_machine_id()
    return verify_license(email, machine_id, key)


class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("License Activation")
        self.setModal(True)

        layout = QFormLayout(self)

        self.email_edit = QLineEdit()
        self.machine_id_edit = QLineEdit()
        self.license_key_edit = QLineEdit()

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
        machine_id = self.machine_id_edit.text().strip()

        if not email or not license_key:
            QMessageBox.warning(self, "Error", "Please fill in all fields.")
            return

        if verify_license(email, machine_id, license_key):
            save_license(email, license_key)
            QMessageBox.information(self, "Success", "License activated successfully.")
            self.accept()
        else:
            QMessageBox.critical(self, "Invalid license", "The license key is invalid for this machine.")
