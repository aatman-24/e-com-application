#!/usr/bin/env python3
"""
flipkart_label_cropper.py

- Takes an input Flipkart PDF (1-up labels with invoice below)
- For each page:
    * finds the "Tax Invoice" text
    * keeps everything ABOVE that (i.e. the label area)
    * tightens the bounding box around the label content
    * creates a NEW page whose size == label size (no margins)
- Writes all cropped pages to an output PDF.
"""

import fitz  # PyMuPDF
import os

# how many points *above* the "Tax Invoice" block we cut
CUT_ABOVE_TAX = 10  # tweak if needed

TINY_MARGIN = 4  # points ≈ 1.4 mm (very small, printer-safe)


def compute_label_rect(page):
    """
    For a Flipkart label page:
      1) find 'Tax Invoice'
      2) keep everything above it
      3) tighten to the union of text/drawings/images in that region
    Returns a fitz.Rect with the final label bounding box.
    """
    full = page.rect

    # 1) find 'Tax Invoice'
    hits = page.search_for("Tax Invoice")
    if not hits:
        # fallback: keep top ~60% of page if text not found
        cut_y = full.y0 + (full.height * 0.6)
    else:
        # we want the *top* of the first 'Tax Invoice' occurrence
        tax_top = min(r.y0 for r in hits)
        cut_y = max(full.y0, tax_top - CUT_ABOVE_TAX)

    # initial region: whole width, only above cut_y
    region = fitz.Rect(full.x0, full.y0, full.x1, cut_y)

    # 2) tighten bbox to actual content inside that region
    bbox = None

    # text blocks
    for b in page.get_text("blocks") or []:
        r = fitz.Rect(b[:4])
        if r.intersects(region):
            bbox = r if bbox is None else bbox | r

    # drawings (lines, boxes, etc.)
    try:
        for d in page.get_drawings():
            r = d.get("rect")
            if r and r.intersects(region):
                bbox = r if bbox is None else bbox | r
    except Exception:
        pass

    # images (logos, QR, barcodes)
    for img in page.get_images(full=True):
        try:
            r = page.get_image_bbox(img[0])
            if r and r.intersects(region):
                bbox = r if bbox is None else bbox | r
        except Exception:
            pass

    if bbox is None:
        # if we somehow got nothing, fall back to region
        bbox = region

    # final safety: clamp to page rect
    bbox = bbox & full
    return bbox


def crop_flipkart_labels(input_pdf, output_pdf):
    """
    Crop each page of input_pdf to the Flipkart label area (no invoice),
    resize the page so it exactly matches the label size, and write
    all pages to output_pdf.
    """
    if not os.path.exists(input_pdf):
        print(f"❌ Input not found: {input_pdf}")
        return

    src = fitz.open(input_pdf)
    out = fitz.open()

    for i in range(src.page_count):
        page = src.load_page(i)

        label_rect = compute_label_rect(page)

        new_page = out.new_page(
            width=label_rect.width + 2 * TINY_MARGIN,
            height=label_rect.height + 2 * TINY_MARGIN
        )

        # destination rect with tiny margin inset
        dest = fitz.Rect(
            TINY_MARGIN,
            TINY_MARGIN,
            new_page.rect.width - TINY_MARGIN,
            new_page.rect.height - TINY_MARGIN
        )

        new_page.show_pdf_page(dest, src, i, clip=label_rect)


    out.save(output_pdf)
    out.close()
    src.close()
    print(f"✅ Cropped Flipkart labels saved to: {output_pdf}")


if __name__ == "__main__":
    # quick manual test
    in_path = "data/flipkart_sample_2.pdf"   # <-- change to your input file
    out_path = "output/flipkart_cropped_2.pdf"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    crop_flipkart_labels(in_path, out_path)
