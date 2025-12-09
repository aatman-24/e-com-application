#!/usr/bin/env python3
"""
flipkart_label_cropper.py

Crop Flipkart labels by removing invoice section and fitting
the shipping label into a 100x100 mm (4x4 inch) PDF page.
"""

import fitz  # PyMuPDF
import os
from datetime import datetime

# -------------------------------
# CONFIG
# -------------------------------
LABEL_W_MM = 100.0
LABEL_H_MM = 100.0
MM_TO_PT = 72.0 / 25.4
LABEL_W = LABEL_W_MM * MM_TO_PT
LABEL_H = LABEL_H_MM * MM_TO_PT

CUT_ABOVE_TAX = 10   # ✅ You confirmed this works well


# -------------------------------
# CORE FUNCTION
# -------------------------------
def crop_flipkart_labels(input_pdf, output_pdf):
    """
    For each page:
      1) Find 'Tax Invoice'
      2) Crop everything BELOW it (invoice + dashed line)
      3) Scale remaining label to fill 4x4 inch page
    """

    if not os.path.exists(input_pdf):
        print(f"⚠️ File not found: {input_pdf}")
        return

    src = fitz.open(input_pdf)
    out = fitz.open()

    for i in range(src.page_count):
        page = src.load_page(i)
        page_rect = page.rect

        # ------------------------------------
        # FIND "Tax Invoice" ANCHOR
        # ------------------------------------
        rects = page.search_for("Tax Invoice")

        if rects:
            # take top-most Tax Invoice
            tax_y = min(r.y0 for r in rects)
            cut_y = max(page_rect.y0, tax_y - CUT_ABOVE_TAX)
            crop_rect = fitz.Rect(
                page_rect.x0,
                page_rect.y0,
                page_rect.x1,
                cut_y
            )
        else:
            # fallback (rare)
            crop_rect = page_rect

        if crop_rect.height <= 0 or crop_rect.width <= 0:
            print(f"⚠️ Skipping page {i}: invalid crop area")
            continue

        # ------------------------------------
        # CREATE 4×4 LABEL PAGE
        # ------------------------------------
        label_page = out.new_page(width=LABEL_W, height=LABEL_H)

        cw, ch = crop_rect.width, crop_rect.height

        scale_x = LABEL_W / cw
        scale_y = LABEL_H / ch
        scale = max(scale_x, scale_y)  # ✅ preserve full label

        sw, sh = cw * scale, ch * scale

        # center in 4x4 page
        dx = (LABEL_W - sw) / 2
        dy = (LABEL_H - sh) / 2

        dest_rect = fitz.Rect(dx, dy, dx + sw, dy + sh)

        label_page.show_pdf_page(
            dest_rect,
            src,
            i,
            clip=crop_rect
        )

    out.save(output_pdf)
    out.close()
    src.close()

    print(f"✅ Flipkart labels cropped & fitted → {output_pdf}")


# -------------------------------
# STANDALONE RUN
# -------------------------------
if __name__ == "__main__":
    INPUT_PDF = "data/flipkart_sample.pdf"   # 🔁 change this
    os.makedirs("output", exist_ok=True)

    ts = datetime.now().strftime("%d-%b-%Y_%H%M%S").lower()
    OUTPUT_PDF = f"output/flipkart_label_4x4_{ts}.pdf"

    crop_flipkart_labels(INPUT_PDF, OUTPUT_PDF)

