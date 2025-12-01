import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import PromptManagerUI

def load_dark_theme(app):
    """Apply the dark theme QSS to the app."""
    try:
        with open("ui/dark_theme.qss", "r") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print("⚠️ Could not load dark theme:", e)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Load dark theme
    load_dark_theme(app)

    window = PromptManagerUI()
    window.show()
    sys.exit(app.exec_())
