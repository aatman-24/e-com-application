import fitz
import os
import re
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


def generate_detailed_summary(labels_pdf, summary_output_pdf=None):
    """
    Read all pages from labels_pdf, aggregate information and create a new PDF
    containing all original pages + one summary page at the end.

    Summary layout (similar to screenshot):
      - ORD QTY Size Color SKU
      - Total package
      - Courier wise total package
      - Company wise total package

    Returns the path to the new PDF (summary_output_pdf).
    """
    if not os.path.exists(labels_pdf):
        print(f"⚠️ Summary: file not found: {labels_pdf}")
        return None

    # open input labels pdf
    src = fitz.open(labels_pdf)

    # ---------- regex patterns ----------
    # VERY generic, adjust if your labels use slightly different words
    qty_pat = re.compile(r'\bQty\s*[:\-]?\s*([0-9]+)', re.IGNORECASE)
    size_pat = re.compile(r'\bSize\s*[:\-]?\s*[:\-]?\s*(.+)', re.IGNORECASE)
    color_pat = re.compile(r'\bColor\s*[:\-]?\s*(.+)', re.IGNORECASE)
    sku_pat = re.compile(r'\b[a-zA-Z0-9_]+(?:\s*[A-Z0-9]+)*\b')  # fallback, but we’ll try better
    # Your old SKU pattern – use it first:
    strict_sku_pat = re.compile(r'\b[a-zA-Z0-9_]+_[a-zA-Z0-9_]+_[a-zA-Z0-9_]+\b')

    courier_pat = re.compile(r'\bCourier\s*Partner\s*[:\-]?\s*(.+)', re.IGNORECASE)
    sold_by_pat = re.compile(r'\bSold\s*By\s*[:\-]?\s*(.+)', re.IGNORECASE)

    # ---------- aggregation containers ----------
    # key: (size, color, sku, qty) → ORD (number of labels)
    main_table = collections.Counter()
    # courier → package count
    courier_counts = collections.Counter()
    # company (sold by) → package count
    company_counts = collections.Counter()

    total_labels = 0

    for page_index in range(src.page_count):
        page = src.load_page(page_index)
        txt = page.get_text("text") or ""
        if not txt.strip():
            continue

        total_labels += 1

        # helper: get first match on a single line
        def _first_line(pat):
            m = pat.search(txt)
            if not m:
                return ""
            # capture only up to end-of-line
            line = m.group(1)
            return line.splitlines()[0].strip()

        # QTY
        qty_match = qty_pat.search(txt)
        qty = int(qty_match.group(1)) if qty_match else 1

        # Size, Color
        size = _first_line(size_pat) or "NA"
        color = _first_line(color_pat) or "NA"

        # SKU – try strict pattern first, fallback to looser pattern
        strict_skus = strict_sku_pat.findall(txt)
        if strict_skus:
            sku = strict_skus[0]
        else:
            skus = sku_pat.findall(txt)
            sku = skus[0] if skus else "UNKNOWN"

        # courier partner
        courier = _first_line(courier_pat) or "Unknown"

        # sold by / company
        sold_by = _first_line(sold_by_pat) or "Unknown"

        main_table[(size, color, sku, qty)] += 1
        courier_counts[courier] += 1
        company_counts[sold_by] += 1

    if not main_table:
        print("ℹ️ Summary: no labels found, skipping summary creation.")
        src.close()
        return None

    # ---------- sort and prepare lines ----------
    # sort by SKU, then color, then size
    rows = []
    for (size, color, sku, qty), ord_count in main_table.items():
        rows.append((ord_count, qty, size, color, sku))
    rows.sort(key=lambda r: (r[4].lower(), r[3].lower(), r[2].lower()))

    # main summary lines
    lines = []

    # header text like your screenshot (customize as you like)
    date_str = datetime.now().strftime("%d, %b %Y")
    lines.append(f"This Meesho label is cropped by pdfcroppers.com on {date_str}")
    lines.append("")  # blank line

    # table header
    header = f"{'ORD':>4} {'QTY':>4} {'Size':<12} {'Color':<12} SKU"
    lines.append(header)
    lines.append("-" * max(len(header), 60))

    for ord_count, qty, size, color, sku in rows:
        lines.append(f"{ord_count:>4} {qty:>4} {size:<12.12} {color:<12.12} {sku}")

    lines.append("")
    lines.append(f"Total package: {total_labels}")
    lines.append("")

    # Courier wise table
    lines.append("Courier wise total package:")
    lines.append(f"{'Package':>7}  Courier Partner")
    lines.append("-" * 35)
    for courier, cnt in sorted(courier_counts.items(), key=lambda x: x[0].lower()):
        lines.append(f"{cnt:>7}  {courier}")
    lines.append("")

    # Company wise table
    lines.append("Company wise total package:")
    lines.append(f"{'Package':>7}  Sold By")
    lines.append("-" * 35)
    for comp, cnt in sorted(company_counts.items(), key=lambda x: x[0].lower()):
        lines.append(f"{cnt:>7}  {comp}")

    full_text = "\n".join(lines)

    # ---------- build summary page ----------
    # Use same page size as first label page
    first_rect = src[0].rect if src.page_count else fitz.Rect(0, 0, 595, 842)  # A4 fallback
    summary_doc = fitz.open()
    page = summary_doc.new_page(width=first_rect.width, height=first_rect.height)

    margin = 36  # ~0.5 inch
    rect = fitz.Rect(
        margin,
        margin,
        page.rect.width - margin,
        page.rect.height - margin
    )

    page.insert_textbox(
        rect,
        full_text,
        fontname="courier",
        fontsize=9,
        align=0  # left
    )

    # ---------- write final PDF: labels + summary ----------
    if summary_output_pdf is None:
        base, ext = os.path.splitext(labels_pdf)
        summary_output_pdf = f"{base}_summary{ext}"

    out = fitz.open()
    out.insert_pdf(src)          # all original labels
    out.insert_pdf(summary_doc)  # last page is summary

    out.save(summary_output_pdf)   # full rewrite, NO incremental save
    out.close()
    src.close()
    summary_doc.close()

    print(f"✅ Summary PDF generated: {summary_output_pdf}")
    return summary_output_pdf


def extract_items_from_label_lines(lines):
    """
    From a list of text 'lines' of a single label page, extract all
    (sku, size, qty, color, order_no) rows under the
    'SKU / Size / Qty / Color / Order No.' header.

    Works for single items AND combo orders (multiple rows).
    """
    items = []

    # normalise whitespace
    lines = [l.strip() for l in lines if l.strip()]

    # 1) locate header "Order No."
    try:
        idx = lines.index("Order No.")
    except ValueError:
        return items  # no product table on this page

    j = idx + 1

    # 2) walk in groups of 5 until we hit next section
    while j + 4 < len(lines):
        sku   = lines[j].strip()
        size  = lines[j + 1].strip()
        qty   = lines[j + 2].strip()
        color = lines[j + 3].strip()
        order = lines[j + 4].strip()

        # stopping conditions: we ran into the next section,
        # or qty is not numeric (then we are out of the table)
        if sku in ("TAX INVOICE", "BILL TO / SHIP TO", "Description"):
            break
        if not qty.replace(" ", "").isdigit():
            break

        items.append((sku, size, qty, color, order))
        j += 5

    return items



def append_summary_page(labels_pdf):
    """
    Append summary page into SAME PDF using incremental save.

    ORD = number of orders having same (SKU, Size, Qty)
    Also shows:
      - Courier wise total package
      - Company wise total package
    """

    if not os.path.exists(labels_pdf):
        print(f"⚠️ Summary: file not found: {labels_pdf}")
        return

    doc = fitz.open(labels_pdf)

    # -------- STORAGE --------
    sku_groups = defaultdict(list)       # (sku, size, qty) -> [order_no, ...]
    courier_counts = defaultdict(int)
    company_counts = defaultdict(int)

    known_couriers = {
        "Delhivery", "Xpressbees", "Xpress Bees", "Shadowfax",
        "Ekart", "Valmo", "Bluedart", "Ecom Express"
    }

    # -------- EXTRACT DATA FROM EACH PAGE --------
    for page in doc:
        text = page.get_text("text") or ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            continue

        # ---- Product row extraction (after Order No.) ----
        try:
            idx = lines.index("Order No.")
        except ValueError:
            continue

        if len(lines) <= idx + 5:
            continue

        sku = lines[idx + 1]
        size = lines[idx + 2]
        qty_raw = lines[idx + 3]
        order_no = lines[idx + 5]

        m = re.search(r"\d+", qty_raw)
        qty = int(m.group()) if m else 1

        sku_groups[(sku, size, qty)].append(order_no)




        courier = extract_courier(lines)
        courier_counts[courier] += 1

        # ---- Company / Sold-by detection ----
        company = "Unknown"
        for i, ln in enumerate(lines):
            if ln == "If undelivered, return to:":
                # next non-empty line is company name
                for j in range(i + 1, len(lines)):
                    if lines[j]:
                        company = lines[j]
                        break
                break
        company_counts[company] += 1

    if not sku_groups:
        print("ℹ️ Summary: no label data found.")
        doc.close()
        return

    # -------- BUILD SUMMARY TEXT --------
    lines_out = []
    lines_out.append("LABEL SUMMARY")
    lines_out.append("")
    lines_out.append(f"Generated: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}")
    lines_out.append("")

    # ---- MAIN SUMMARY TABLE ----
    header = f"{'ORD':>5} {'QTY':>5} {'Size':<15} {'SKU'}"
    lines_out.append(header)
    lines_out.append("-" * len(header))

    total_packages = 0

    for (sku, size, qty), orders in sorted(
        sku_groups.items(), key=lambda x: (x[0][0].lower(), x[0][1].lower())
    ):
        ord_count = len(orders)
        total_packages += ord_count
        lines_out.append(
            f"{ord_count:>5} {qty:>5} {size[:14]:<15} {sku}"
        )

    lines_out.append("")
    lines_out.append(f"Total package: {total_packages}")
    lines_out.append("")

    # ---- COURIER SUMMARY ----
    lines_out.append("Courier wise total package:")
    lines_out.append(f"{'Package':>7}  Courier Partner")
    for courier, cnt in sorted(courier_counts.items(), key=lambda x: x[0].lower()):
        lines_out.append(f"{cnt:>7}  {courier}")

    lines_out.append("")

    # ---- COMPANY SUMMARY ----
    lines_out.append("Company wise total package:")
    lines_out.append(f"{'Package':>7}  Sold By")
    for company, cnt in sorted(company_counts.items(), key=lambda x: x[0].lower()):
        lines_out.append(f"{cnt:>7}  {company}")

    summary_text = "\n".join(lines_out)

    # -------- ADD SUMMARY PAGE --------
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

    # -------- SAVE INTO SAME FILE (ONLY VALID WAY) --------
    doc.save(
        labels_pdf,
        incremental=True,
        encryption=fitz.PDF_ENCRYPT_KEEP
    )
    doc.close()

    print("✅ Summary page appended with SKU + Courier + Company info.")


def extract_courier(lines):
    """
    Extract courier by:
    - Finding the line 'Pickup'
    - Taking the closest previous non-empty line as courier name
    """

    for i, ln in enumerate(lines):
        if ln.strip().lower() == "pickup":
            # find previous non-empty line
            j = i - 1
            while j >= 0:
                prev = lines[j].strip()
                if prev:
                    return normalize_courier(prev)
                j -= 1

    return "Unknown"


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

    # # Normalize Valmo family
    # if "valmo" in low:
    #     return "Valmo"

    # # Normalize common spelling variants
    # if "xpress" in low:
    #     return "Xpressbees"
    # if "delhivery" in low:
    #     return "Delhivery"

    # # Fallback: return raw line
    # return raw_name


# ==========================================================
# MAIN DRIVER — COMBINE BOTH STEPS
# ==========================================================
if __name__ == "__main__":
    now = datetime.now()
    hour_str = now.strftime("%H")
    date_str = now.strftime("%d-%b-%Y").lower()
    os.makedirs("output", exist_ok=True)

    input_files = ["data/1.pdf", "data/3.pdf"]
    merged_input_pdf = f"output/test/{date_str}_merged_{hour_str}.pdf"
    temp_sorted_pdf = f"output/test/{date_str}_sorted_{hour_str}.pdf"
    final_output_pdf = f"output/test/{date_str}_label_{hour_str}.pdf"
    sku_mapping_csv = os.path.join(BASE_DIR, "data", "sku_mapping.csv")
    print("\n🌀 Starting label processing...")
    merge_input_pdfs(input_files, merged_input_pdf)
    sort_pdf_by_parent_sku(merged_input_pdf, sku_mapping_csv, temp_sorted_pdf)
    crop_and_fit_labels(temp_sorted_pdf, final_output_pdf)
    print(f"\n🎯 Done! Final label PDF: {final_output_pdf}")

    # NEW: append summary page when running standalone
    append_summary_page(final_output_pdf, sku_mapping_csv)

