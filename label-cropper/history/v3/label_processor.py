import fitz  # PyMuPDF
import pandas as pd
import re
from datetime import datetime
import os

# ==========================================================
# STEP 0 — MERGE MULTIPLE INPUT FILES
# ==========================================================
def merge_input_pdfs(input_files, merged_output_path):
    """Merge multiple PDFs into one combined file."""
    merged = fitz.open()
    for pdf_path in input_files:
        if not os.path.exists(pdf_path):
            print(f"⚠️ Skipping missing file: {pdf_path}")
            continue
        doc = fitz.open(pdf_path)
        merged.insert_pdf(doc)
    merged.save(merged_output_path)
    print(f"✅ Merged {len(input_files)} PDFs → {merged_output_path}")
    return merged_output_path


# ==========================================================
# STEP 1 — SORT LABELS BY PARENT/CHILD SKU + COMBO PRIORITY
# ==========================================================
def sort_pdf_by_parent_sku(input_pdf, sku_mapping_csv, temp_sorted_pdf):
    mapping_df = pd.read_csv(sku_mapping_csv)
    mapping_df.columns = [c.strip().lower().replace(" ", "_") for c in mapping_df.columns]

    if not {'parent_sku', 'child_sku'}.issubset(mapping_df.columns):
        raise ValueError(f"CSV must contain columns ['parent_sku', 'child_sku']")

    child_to_parent = dict(zip(mapping_df['child_sku'], mapping_df['parent_sku']))
    doc = fitz.open(input_pdf)

    sku_pattern = re.compile(r'\b[a-zA-Z0-9_]+_[a-zA-Z0-9_]+_[a-zA-Z0-9_]+\b')
    qty_pattern = re.compile(r'\bQty\s*([0-9]+)\b', re.IGNORECASE)

    page_info = []

    for i, page in enumerate(doc):
        text = page.get_text("text") or ""
        skus = sku_pattern.findall(text)
        qty_match = qty_pattern.search(text)
        qty = int(qty_match.group(1)) if qty_match else 1
        is_combo = len(skus) > 1 or qty > 1

        if not skus:
            page_info.append((i, "zzzzzz", f"unknown_{i:06d}", False))
            continue

        sku = skus[0]
        parent = child_to_parent.get(sku, sku)
        page_info.append((i, parent, sku, is_combo))

    sorted_pages = sorted(page_info, key=lambda x: (not x[3], x[1].lower(), x[2].lower()))
    new_doc = fitz.open()

    for page_index, parent, sku, is_combo in sorted_pages:
        new_doc.insert_pdf(doc, from_page=page_index, to_page=page_index)

    new_doc.save(temp_sorted_pdf)
    print(f"✅ Sorted PDF saved: {temp_sorted_pdf} ({len(page_info)} pages)")
    return temp_sorted_pdf


# ==========================================================
# STEP 2 — AUTO-SCALE & FIT TO 100×100 mm, KEEP SKU PAGES
# ==========================================================
def crop_and_fit_labels(input_pdf, output_pdf):
    """Crop white space, shrink large content to fit 100×100 mm, and keep only 'SKU' pages."""
    LABEL_W_MM = 100.0
    LABEL_H_MM = 100.0
    MM_TO_PT = 72.0 / 25.4
    LABEL_W = LABEL_W_MM * MM_TO_PT
    LABEL_H = LABEL_H_MM * MM_TO_PT
    OUTER_MARGIN = 0.5 * MM_TO_PT
    INNER_PADDING = 0.5 * MM_TO_PT

    sku_pattern = re.compile(r'\b[a-zA-Z0-9_]+_[a-zA-Z0-9_]+_[a-zA-Z0-9_]+\b')
    sku_title_pattern = re.compile(r'\bSKU\b', re.IGNORECASE)

    src_doc = fitz.open(input_pdf)
    temp_doc = fitz.open()

    for page_index in range(src_doc.page_count):
        src_page = src_doc.load_page(page_index)
        text = src_page.get_text("text") or ""

        bbox = None
        for b in src_page.get_text("blocks") or []:
            r = fitz.Rect(b[:4])
            bbox = r if bbox is None else bbox | r

        try:
            for d in src_page.get_drawings():
                r = d.get("rect")
                if r:
                    bbox = r if bbox is None else bbox | r
        except Exception:
            pass

        for img in src_page.get_images(full=True):
            try:
                r = src_page.get_image_bbox(img[0])
                if r:
                    bbox = r if bbox is None else bbox | r
            except Exception:
                pass

        if bbox is None or bbox.is_empty:
            bbox = src_page.rect

        bbox = bbox + (-INNER_PADDING, -INNER_PADDING, INNER_PADDING, INNER_PADDING)
        bbox.intersect(src_page.rect)

        new_page = temp_doc.new_page(width=LABEL_W, height=LABEL_H)
        usable = fitz.Rect(OUTER_MARGIN, OUTER_MARGIN, LABEL_W - OUTER_MARGIN, LABEL_H - OUTER_MARGIN)
        inner = fitz.Rect(
            usable.x0 + INNER_PADDING,
            usable.y0 + INNER_PADDING,
            usable.x1 - INNER_PADDING,
            usable.y1 - INNER_PADDING
        )

        content_w, content_h = bbox.width, bbox.height
        target_w, target_h = inner.width, inner.height

        scale_x = target_w / content_w if content_w else 1.0
        scale_y = target_h / content_h if content_h else 1.0
        scale = min(scale_x, scale_y, 1.0)

        scaled_w = content_w * scale
        scaled_h = content_h * scale
        offset_x = inner.x0 + (inner.width - scaled_w) / 2
        offset_y = inner.y0 + (inner.height - scaled_h) / 2
        dest_rect = fitz.Rect(offset_x, offset_y, offset_x + scaled_w, offset_y + scaled_h)

        new_page.show_pdf_page(dest_rect, src_doc, page_index, clip=bbox)

    final_doc = fitz.open()
    for i in range(temp_doc.page_count):
        p = temp_doc.load_page(i)
        t = p.get_text("text") or ""
        if sku_title_pattern.search(t):
            final_doc.insert_pdf(temp_doc, from_page=i, to_page=i)

    final_doc.save(output_pdf)
    print(f"✅ Cropped & scaled final PDF saved: {output_pdf}")


# ==========================================================
# MAIN DRIVER — COMBINE BOTH STEPS
# ==========================================================
if __name__ == "__main__":
    now = datetime.now()
    hour_str = now.strftime("%H")
    date_str = now.strftime("%d-%b-%Y").lower()
    os.makedirs("output", exist_ok=True)

    input_files = ["data/1.pdf", "data/3.pdf"]
    merged_input_pdf = f"output/{date_str}_merged_{hour_str}.pdf"
    temp_sorted_pdf = f"output/{date_str}_sorted_{hour_str}.pdf"
    final_output_pdf = f"output/{date_str}_label_{hour_str}.pdf"
    sku_mapping_csv = "data/sku_mapping.csv"

    print("\n🌀 Starting label processing...")
    merge_input_pdfs(input_files, merged_input_pdf)
    sort_pdf_by_parent_sku(merged_input_pdf, sku_mapping_csv, temp_sorted_pdf)
    crop_and_fit_labels(temp_sorted_pdf, final_output_pdf)
    print(f"\n🎯 Done! Final label PDF: {final_output_pdf}")
