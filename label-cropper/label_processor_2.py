import fitz
import os
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import pandas as pd  # only needed if you still want parent_sku mapping


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

    sku_title_pattern = re.compile(r'\bSKU\b', re.IGNORECASE)

    src_doc = fitz.open(input_pdf)
    temp_doc = fitz.open()

    for page_index in range(src_doc.page_count):
        src_page = src_doc.load_page(page_index)

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
# HELPERS FOR SUMMARY
# ==========================================================
def extract_items_from_label_lines(lines):
    """
    From a list of text 'lines' of a single label page, extract all
    (sku, size, qty, color, order_no) rows under the
    'SKU / Size / Qty / Color / Order No.' header.

    Works for single items AND combo orders (multiple rows).
    """
    items = []

    lines = [l.strip() for l in lines if l.strip()]

    # locate header "Order No."
    try:
        idx = lines.index("Order No.")
    except ValueError:
        return items  # no product table on this page

    j = idx + 1

    # walk in groups of 5 until we hit next section
    while j + 4 < len(lines):
        sku   = lines[j].strip()
        size  = lines[j + 1].strip()
        qty   = lines[j + 2].strip()
        color = lines[j + 3].strip()
        order = lines[j + 4].strip()

        if sku in ("TAX INVOICE", "BILL TO / SHIP TO", "Description"):
            break
        if not qty.replace(" ", "").isdigit():
            break

        items.append((sku, size, qty, color, order))
        j += 5

    return items



def normalize_courier(raw_name: str) -> str:
    low = raw_name.lower()

    if re.search(r"valmo", raw_name, re.IGNORECASE):
        return "Valmo"

    # optional normalizations
    if re.search(r"xpress", raw_name, re.IGNORECASE):
        return "Xpressbees"
    if re.search(r"delhivery", raw_name, re.IGNORECASE):
        return "Delhivery"

    return raw_name


def extract_courier(lines):
    """
    Extract courier by:
    - finding the line 'Pickup'
    - taking the closest previous non-empty line as courier name
    """
    for i, ln in enumerate(lines):
        if ln.strip().lower() == "pickup":
            j = i - 1
            while j >= 0:
                prev = lines[j].strip()
                if prev:
                    return normalize_courier(prev)
                j -= 1
    return "Unknown"


# ==========================================================
# STEP 3 — APPEND SUMMARY PAGE (IN SAME FILE)
# ==========================================================
def append_summary_page(labels_pdf):
    """
    Append summary page into SAME PDF using incremental save.

    ORD = number of *orders* having same (SKU, Size, Qty)
    Also shows:
      - Courier wise total package
      - Company wise total package
    """

    if not os.path.exists(labels_pdf):
        print(f"⚠️ Summary: file not found: {labels_pdf}")
        return

    doc = fitz.open(labels_pdf)

    sku_groups = defaultdict(list)    # (sku, size, qty) -> [order_no, ...]
    courier_counts = defaultdict(int)
    company_counts = defaultdict(int)

    for page in doc:
        text = page.get_text("text") or ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            continue

        # items table (handles combo orders)
        items = extract_items_from_label_lines(lines)
        for sku, size, qty_raw, color, order_no in items:
            m = re.search(r"\d+", qty_raw)
            qty = int(m.group()) if m else 1
            sku_groups[(sku, size, qty)].append(order_no)

        # courier using Pickup rule
        courier = extract_courier(lines)
        courier_counts[courier] += 1

        # company from "If undelivered, return to:"
        company = "Unknown"
        # for i, ln in enumerate(lines):
        #     if ln == "If undelivered, return to:":
        #         for j in range(i + 1, len(lines)):
        #             if lines[j]:
        #                 company = lines[j]
        #                 break
        #         break
        company_counts[company] += 1

    if not sku_groups:
        print("ℹ️ Summary: no label data found.")
        doc.close()
        return

    # build summary text
    lines_out = []
    lines_out.append("LABEL SUMMARY")
    lines_out.append("")
    lines_out.append(f"Generated: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}")
    lines_out.append("")

    header = f"{'ORD':>5} {'QTY':>5} {'Size':<15} {'SKU'}"
    lines_out.append(header)
    lines_out.append("-" * len(header))

    total_packages = 0

    for (sku, size, qty), orders in sorted(
        sku_groups.items(), key=lambda x: (x[0][0].lower(), x[0][1].lower(), x[0][2])
    ):
        ord_count = len(set(orders))  # unique orders
        total_packages += ord_count
        lines_out.append(f"{ord_count:>5} {qty:>5} {size[:14]:<15} {sku}")

    lines_out.append("")
    lines_out.append(f"Total package: {total_packages}")
    lines_out.append("")

    # courier summary
    lines_out.append("Courier wise total package:")
    lines_out.append(f"{'Package':>7}  Courier Partner")
    for courier, cnt in sorted(courier_counts.items(), key=lambda x: x[0].lower()):
        lines_out.append(f"{cnt:>7}  {courier}")
    lines_out.append("")

    # company summary
    lines_out.append("Company wise total package:")
    lines_out.append(f"{'Package':>7}  Sold By")
    for company, cnt in sorted(company_counts.items(), key=lambda x: x[0].lower()):
        lines_out.append(f"{cnt:>7}  {company}")

    summary_text = "\n".join(lines_out)

    # add summary page
    page = doc.new_page()
    margin = 36
    rect = fitz.Rect(
        margin,
        margin,
        page.rect.width - margin,
        page.rect.height - margin,
    )

    page.insert_textbox(
        rect,
        summary_text,
        fontname="courier",
        fontsize=9,
        align=0,
    )

    # IMPORTANT: same filename → incremental=True
    doc.save(labels_pdf, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()

    print("✅ Summary page appended with SKU + Courier + Company info.")
    print(f"🎯 Final label PDF: {labels_pdf}")


# ==========================================================
# MAIN DRIVER — COMBINE BOTH STEPS
# ==========================================================
if __name__ == "__main__":
    now = datetime.now()
    hour_str = now.strftime("%H")
    date_str = now.strftime("%d-%b-%Y").lower()
    os.makedirs("output/test", exist_ok=True)

    BASE_DIR = Path.home() / "Downloads" / "daily_label"

    input_files = [f"{BASE_DIR}/1.pdf", f"{BASE_DIR}/2.pdf"]
    merged_input_pdf = f"output/test/{date_str}_merged_{hour_str}.pdf"
    temp_sorted_pdf = f"output/test/{date_str}_sorted_{hour_str}.pdf"
    final_output_pdf = f"output/test/{date_str}_label_{hour_str}.pdf"
    sku_mapping_csv = os.path.join(BASE_DIR, "data", "sku_mapping.csv")

    print("\n🌀 Starting label processing...")
    merge_input_pdfs(input_files, merged_input_pdf)
    sort_pdf_by_parent_sku(merged_input_pdf, sku_mapping_csv, temp_sorted_pdf)
    crop_and_fit_labels(temp_sorted_pdf, final_output_pdf)
    append_summary_page(final_output_pdf)
    print(f"\n🎯 Done! Final label PDF (with summary): {final_output_pdf}")
