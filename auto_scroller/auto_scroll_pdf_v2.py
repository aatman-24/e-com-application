#!/usr/bin/env python3
import sys
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
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage


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
            # When reach bottom, loop back to top
            # bar.setValue(0)

            self.timer.stop()  # stop scrolling at EOF


def main():
    app = QApplication(sys.argv)
    viewer = PdfAutoScrollViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
