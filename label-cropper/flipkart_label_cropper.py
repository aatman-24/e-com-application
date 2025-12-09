#!/usr/bin/env python3
"""
flipkart_label_cropper.py

Crop Flipkart pages that contain BOTH label + invoice on same page,
and generate a new PDF where each page is only the shipping label,
scaled to ~4x4 inches (100x100 mm), similar to your Meesho labels.

No sorting, no summary.
"""

import fitz  # PyMuPDF
import os
from datetime import datetime


import fitz  # PyMuPDF
import os

# def crop_flipkart_labels(input_pdf, output_pdf):
#     """
#     For each page in input_pdf:
#       - Find the position of the text 'Tax Invoice'
#       - Crop everything above that (i.e. remove invoice area)
#       - Fit the cropped label into a 100x100 mm page (like your Meesho labels)
#     Save all processed pages into output_pdf.
#     """

#     if not os.path.exists(input_pdf):
#         print(f"⚠️ Flipkart: file not found: {input_pdf}")
#         return

#     src_doc = fitz.open(input_pdf)

#     # ---- target label size: 100 x 100 mm ----
#     LABEL_W_MM = 100.0
#     LABEL_H_MM = 100.0
#     MM_TO_PT = 72.0 / 25.4
#     LABEL_W = LABEL_W_MM * MM_TO_PT
#     LABEL_H = LABEL_H_MM * MM_TO_PT

#     OUTER_MARGIN = 0.5 * MM_TO_PT
#     INNER_PADDING = 0.5 * MM_TO_PT

#     out_doc = fitz.open()

#     for page_index in range(src_doc.page_count):
#         page = src_doc.load_page(page_index)

#         # 1) Find 'Tax Invoice' (case-insensitive)
#         rects = page.search_for("Tax Invoice")
#         if not rects:
#             rects = page.search_for("Tax\nInvoice")

#         if rects:
#             # smallest y0 = top of the "Tax Invoice" block
#             cut_y = min(r.y0 for r in rects) - 2  # small safety margin
#         else:
#             # fallback: cut at 60% of page height if "Tax Invoice" not found
#             cut_y = page.rect.height * 0.6

#         # avoid negative / insanely small area
#         cut_y = max(cut_y, page.rect.y0 + 10)

#         # 2) Label region: entire width, from top to just before 'Tax Invoice'
#         label_rect = fitz.Rect(
#             page.rect.x0,
#             page.rect.y0,
#             page.rect.x1,
#             cut_y
#         )

#         # 3) Create new 100x100 mm page
#         new_page = out_doc.new_page(width=LABEL_W, height=LABEL_H)

#         usable = fitz.Rect(
#             OUTER_MARGIN,
#             OUTER_MARGIN,
#             LABEL_W - OUTER_MARGIN,
#             LABEL_H - OUTER_MARGIN,
#         )
#         inner = fitz.Rect(
#             usable.x0 + INNER_PADDING,
#             usable.y0 + INNER_PADDING,
#             usable.x1 - INNER_PADDING,
#             usable.y1 - INNER_PADDING,
#         )

#         # 4) Scale label_rect to fit into 'inner'
#         content_w, content_h = label_rect.width, label_rect.height
#         target_w, target_h = inner.width, inner.height

#         if content_w == 0 or content_h == 0:
#             # fallback – just copy the original page scaled down
#             dest_rect = inner
#         else:
#             scale_x = target_w / content_w
#             scale_y = target_h / content_h
#             scale = min(scale_x, scale_y, 1.0)

#             scaled_w = content_w * scale
#             scaled_h = content_h * scale

#             offset_x = inner.x0 + (inner.width - scaled_w) / 2
#             offset_y = inner.y0 + (inner.height - scaled_h) / 2

#             dest_rect = fitz.Rect(
#                 offset_x,
#                 offset_y,
#                 offset_x + scaled_w,
#                 offset_y + scaled_h,
#             )

#         # 5) Copy only the cropped label into the new page
#         new_page.show_pdf_page(
#             dest_rect,
#             src_doc,
#             page_index,
#             clip=label_rect
#         )

#     out_doc.save(output_pdf)
#     out_doc.close()
#     src_doc.close()

#     print(f"✅ Flipkart label-only PDF saved: {output_pdf}")



# import fitz
# import os

# def crop_flipkart_labels(input_pdf, output_pdf):
#     """
#     Crop Flipkart pages by removing the invoice portion.
#     Uses 'Tax Invoice' OR dashed separator line as cut-off.
#     Keeps only the shipping label and fits it into 4x4 inches.
#     """

#     if not os.path.exists(input_pdf):
#         print(f"⚠️ Input file not found: {input_pdf}")
#         return

#     # 4x4 inch target
#     LABEL_W_MM = 100.0
#     LABEL_H_MM = 100.0
#     MM_TO_PT = 72.0 / 25.4
#     LABEL_W = LABEL_W_MM * MM_TO_PT
#     LABEL_H = LABEL_H_MM * MM_TO_PT

#     OUTER_MARGIN = 6
#     INNER_PADDING = 6

#     src = fitz.open(input_pdf)
#     out = fitz.open()

#     for page_index in range(src.page_count):
#         page = src.load_page(page_index)

#         cut_y = None

#         # -------- Rule 1: Tax Invoice text --------
#         rects = page.search_for("Tax Invoice")
#         if rects:
#             cut_y = min(r.y0 for r in rects)

#         # -------- Rule 2: dashed separator line --------
#         if cut_y is None:
#             text = page.get_text("text") or ""
#             for block in page.get_text("blocks") or []:
#                 x0, y0, x1, y1, txt, *_ = block
#                 if txt and "----" in txt:
#                     cut_y = y0
#                     break

#         # -------- Fallback: 55% of page height --------
#         if cut_y is None:
#             cut_y = page.rect.height * 0.55

#         # Safety clamp
#         cut_y = max(page.rect.y0 + 20, cut_y)

#         # Define label crop
#         label_rect = fitz.Rect(
#             page.rect.x0,
#             page.rect.y0,
#             page.rect.x1,
#             cut_y
#         )

#         # ---- Create output 4x4 label page ----
#         new_page = out.new_page(width=LABEL_W, height=LABEL_H)

#         usable = fitz.Rect(
#             OUTER_MARGIN,
#             OUTER_MARGIN,
#             LABEL_W - OUTER_MARGIN,
#             LABEL_H - OUTER_MARGIN
#         )

#         inner = usable + (
#             INNER_PADDING,
#             INNER_PADDING,
#             -INNER_PADDING,
#             -INNER_PADDING
#         )

#         content_w = label_rect.width
#         content_h = label_rect.height

#         scale = min(
#             inner.width / content_w if content_w else 1,
#             inner.height / content_h if content_h else 1,
#             1.0
#         )

#         scaled_w = content_w * scale
#         scaled_h = content_h * scale

#         dx = inner.x0 + (inner.width - scaled_w) / 2
#         dy = inner.y0 + (inner.height - scaled_h) / 2

#         dest = fitz.Rect(dx, dy, dx + scaled_w, dy + scaled_h)

#         new_page.show_pdf_page(dest, src, page_index, clip=label_rect)

#     out.save(output_pdf)
#     out.close()
#     src.close()

#     print(f"✅ Flipkart labels cropped (invoice removed): {output_pdf}")

import fitz  # PyMuPDF
import os

def crop_flipkart_labels(input_pdf, output_pdf):
    """
    For each page of a Flipkart label PDF:
      - Find the 'Tax Invoice' heading.
      - Crop everything below that heading (so dashed line + invoice are removed).
      - Scale the remaining top part to a 4x4 inch label (≈100x100 mm) with NO padding.
    """
    if not os.path.exists(input_pdf):
        print(f"⚠️ Input not found: {input_pdf}")
        return

    # 4x4 inch label (same as your 100x100 mm Meesho labels, close enough)
    MM_TO_PT = 72.0 / 25.4
    LABEL_W_MM = 100.0
    LABEL_H_MM = 100.0
    LABEL_W = LABEL_W_MM * MM_TO_PT
    LABEL_H = LABEL_H_MM * MM_TO_PT

    src = fitz.open(input_pdf)
    out = fitz.open()

    for page_index in range(src.page_count):
        page = src.load_page(page_index)
        page_rect = page.rect

        # --- FIND "Tax Invoice" ---
        # IMPORTANT: no 'hit_max' kw here → your version of PyMuPDF doesn't accept it
        matches = page.search_for("Tax Invoice")   # returns a list of Rects

        if matches:
            # choose the top-most match (smallest y0)
            ti_rect = min(matches, key=lambda r: r.y0)

            # crop from top of page down to the TOP of "Tax Invoice"
            # using y0 removes the dashed line and the invoice block
            crop_rect = fitz.Rect(
                page_rect.x0,
                page_rect.y0,
                page_rect.x1,
                ti_rect.y0
            )
        else:
            # fallback: no 'Tax Invoice' found → use full page
            crop_rect = page_rect

        # --- CREATE 4x4 LABEL PAGE (NO PADDING) ---
        new_page = out.new_page(width=LABEL_W, height=LABEL_H)

        content_w = crop_rect.width
        content_h = crop_rect.height

        # scale so that the cropped area fits entirely inside 4x4, no padding
        # (we center it, but it touches at least one side)
        scale = min(LABEL_W / content_w, LABEL_H / content_h)

        scaled_w = content_w * scale
        scaled_h = content_h * scale

        # center on the new label page
        offset_x = (LABEL_W - scaled_w) / 2.0
        offset_y = (LABEL_H - scaled_h) / 2.0

        dest_rect = fitz.Rect(
            offset_x,
            offset_y,
            offset_x + scaled_w,
            offset_y + scaled_h
        )

        # copy cropped part of original page into the new label page
        new_page.show_pdf_page(
            dest_rect,
            src,
            page_index,
            clip=crop_rect
        )

    out.save(output_pdf)
    out.close()
    src.close()
    print(f"✅ Cropped Flipkart labels saved → {output_pdf}")


# ----------------------------------------------------------
# Simple standalone runner (adjust paths as you like)
# ----------------------------------------------------------
if __name__ == "__main__":
    # Example usage:
    #   python flipkart_label_cropper.py
    # (update input/output paths as needed)
    input_path = "data/flipkart_sample.pdf"
    now = datetime.now()
    stamp = now.strftime("%d-%b-%Y_%H%M%S").lower()
    output_path = f"output/flipkart_labels_{stamp}.pdf"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print("🌀 Cropping Flipkart labels...")
    crop_flipkart_labels(input_path, output_path)
    print("🎯 Done.")
