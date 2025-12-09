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
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage

# ==== SETTINGS YOU CAN CHANGE ====
PDF_PATH = "sample.pdf"     # 👈 put your PDF file path here
AUTO_SCROLL_INTERVAL_MS = 20  # how often to move (milliseconds)
AUTO_SCROLL_STEP = 2          # how many pixels to move each tick
LOOP_AT_END = False            # if True, jump back to top when reaching bottom
# ================================


class PdfAutoScrollViewer(QMainWindow):
    def __init__(self, pdf_path):
        super().__init__()

        self.setWindowTitle("Auto Scrolling PDF Viewer")
        self.resize(900, 700)

        # --- Scroll Area ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.setCentralWidget(self.scroll_area)

        # --- Container widget for PDF pages ---
        self.container = QWidget()
        self.v_layout = QVBoxLayout(self.container)
        self.v_layout.setAlignment(Qt.AlignTop)

        # Load PDF pages as images
        self.load_pdf(pdf_path)

        self.scroll_area.setWidget(self.container)

        # --- Auto scroll timer ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.auto_scroll)
        self.timer.start(AUTO_SCROLL_INTERVAL_MS)

    def load_pdf(self, pdf_path):
        doc = fitz.open(pdf_path)

        for page in doc:
            # Increase matrix for better quality (zoom 1.5x)
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

            # Add some spacing between pages
            self.v_layout.addWidget(label)

        # Little stretch at the bottom
        spacer = QWidget()
        spacer.setFixedHeight(20)
        self.v_layout.addWidget(spacer)

    def auto_scroll(self):
        bar = self.scroll_area.verticalScrollBar()
        current_value = bar.value()
        max_value = bar.maximum()

        if current_value < max_value:
            bar.setValue(current_value + AUTO_SCROLL_STEP)
        else:
            if LOOP_AT_END:
                bar.setValue(0)  # go back to top
            else:
                self.timer.stop()  # stop scrolling when finished


def main():
    app = QApplication(sys.argv)

    # If you want to pass path from command line:
    # python auto_scroll_pdf.py myfile.pdf
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = PDF_PATH

    viewer = PdfAutoScrollViewer(pdf_path)
    viewer.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
