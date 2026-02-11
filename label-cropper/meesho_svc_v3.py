#!/usr/bin/env python3
"""
final_meesho_flipkart_service.py

Single-pass label processor:
- Groups labels by courier (Delivery → Valmo → Express → Others → Unknown)
- Sorts alphabetically by SKU inside each courier group
- Skips pages without SKU
- Crops & fits to 100x100mm
- Adds border
- Appends summary pages
"""

import os
import re
from collections import defaultdict
from datetime import datetime
from typing import List

import fitz  # PyMuPDF

# ==========================================================
# CONSTANTS
# ==========================================================
MM_TO_PT = 72.0 / 25.4
LABEL_W = 100.0 * MM_TO_PT
LABEL_H = 100.0 * MM_TO_PT
OUTER_MARGIN = 0.3 * MM_TO_PT
INNER_PADDING = 0.1 * MM_TO_PT
BORDER_GAP = 4  # points (~1.4 mm). Change to 3 or 5 if needed
BORDER_MIN_INSET = 1


SKU_FIELD = re.compile(r'\b[a-zA-Z0-9_]+_[a-zA-Z0-9_]+_[a-zA-Z0-9_]+\b')
ORDER_HEADER_RE = re.compile(r'\bOrder\s*No\.?\b', re.IGNORECASE)


DEBUG = True
DEBUG_PAGE = 6   # set to page number later (0-based)


# ==========================================================
# MERGE PDFs
# ==========================================================
def merge_input_pdfs(input_files: List[str], merged_output_path: str) -> str:
    merged = fitz.open()
    for f in input_files:
        if os.path.exists(f):
            d = fitz.open(f)
            merged.insert_pdf(d)
            d.close()
    merged.save(merged_output_path)
    merged.close()
    return merged_output_path


# ==========================================================
# HELPERS
# ==========================================================
def _parse_lines(page) -> List[str]:
    raw = page.get_text("rawdict")
    lines = []
    for block in raw.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            spans = [s["text"].strip() for s in line.get("spans", []) if s.get("text", "").strip()]
            if spans:
                lines.append(" ".join(spans))
    if not lines:
        txt = page.get_text("text") or ""
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
    return lines


def extract_courier(lines: List[str]) -> str:
    def norm(v: str) -> str:
        v = v.lower()
        if "valmo" in v: return "Valmo"
        if "xpress" in v or "ecom" in v: return "Express"
        if "delhivery" in v or "delivery" in v: return "Delivery"
        if "ekart" in v: return "Ekart"
        if "shadowfax" in v: return "Shadowfax"
        if "bluedart" in v: return "Bluedart"
        return v.title()

    for i, ln in enumerate(lines):
        low = ln.lower()
        if "pickup" in low:
            if "valmo" in low:
                return "Valmo"
            j = i - 1
            while j >= 0:
                if lines[j].strip():
                    return norm(lines[j])
                j -= 1

    return "Unknown"


def courier_priority(courier: str) -> int:
    c = courier.lower()
    if "delivery" in c: return 0
    if "valmo" in c: return 1
    if "express" in c or "xpress" in c or "ecom" in c: return 2
    if c == "unknown": return 4
    return 3


def extract_sku_from_lines(lines):
    """
    Reliable SKU extraction:
    1) Look for 'Order No.' table
    2) SKU is the first row after header
    """
    lines = [l.strip() for l in lines if l.strip()]

    try:
        idx = next(i for i, l in enumerate(lines) if ORDER_HEADER_RE.search(l))
    except StopIteration:
        return None, None  # sku, qty

    # Table format:
    # SKU
    # Size
    # Qty
    # Color
    # Order No
    if idx + 3 >= len(lines):
        return None, None

    sku = lines[idx + 1].strip()
    qty_line = lines[idx + 3].strip()

    m = re.search(r'\d+', qty_line)
    qty = int(m.group()) if m else 1

    return sku, qty

def is_valid_label_page(sku: str, courier: str) -> bool:
    if not sku:
        return False
    if not courier or courier == "Unknown":
        return False
    return True


def process_flipkart_labels(input_files: List[str], out_dir: str) -> str:
    """
    Convenience helper for the UI:
      1) merge selected PDFs
      2) crop Flipkart labels
    """
    os.makedirs(out_dir, exist_ok=True)
    now = datetime.now()
    date_str = now.strftime("%d-%b-%Y").lower()
    time_str = now.strftime("%H%M%S")
    merged_pdf = os.path.join(out_dir, f"{date_str}_flipkart_merged_{time_str}.pdf")
    final_pdf = os.path.join(out_dir, f"{date_str}_flipkart_label_{time_str}.pdf")
    merge_input_pdfs(input_files, merged_pdf)
    crop_flipkart_labels(merged_pdf, final_pdf)
    try:
        os.remove(merged_pdf)
    except Exception:
        pass
    return final_pdf



# ==========================================================
# MAIN SINGLE-PASS PROCESSOR
# ==========================================================
def process_labels_single_pass(input_pdf: str, out_pdf: str, append_summary: bool = True) -> str:
    doc = fitz.open(input_pdf)

    pages = []
    skipped = 0

    sku_groups = defaultdict(int)

    courier_counts = defaultdict(int)
    company_counts = defaultdict(int)

    for i in range(doc.page_count):
        page = doc[i]
        lines = _parse_lines(page)

        if DEBUG and (DEBUG_PAGE is None or DEBUG_PAGE == i):
            print("\n" + "=" * 60)
            print(f"DEBUG PAGE {i}")
            print("=" * 60)
            for idx, ln in enumerate(lines):
                print(f"{idx:02d} | {ln}")

        # -----------------------------
        # 1️⃣ Courier
        # -----------------------------
        courier = extract_courier(lines)

        # -----------------------------
        # 2️⃣ Extract product rows (TABLE FIRST, THEN FALLBACK)
        # -----------------------------
        rows = extract_product_rows(lines)

        if DEBUG and (DEBUG_PAGE is None or DEBUG_PAGE == i):
            print(rows)


        # fallback if product table parsing fails
        if not rows:
            skus = SKU_FIELD.findall(" ".join(lines))
            if not skus:
                skipped += 1
                continue

            # fake one row so page still processes
            rows = [(skus[0], "", 1, "")]

        # -----------------------------
        # 3️⃣ SUMMARY AGGREGATION (THIS IS THE ONLY PLACE)
        # -----------------------------
        for sku, size, qty, color in rows:
            sku_groups[(courier, sku, qty, size, color)] += 1


        # -----------------------------
        # 3️⃣ Page-level metadata (FIRST row)
        # -----------------------------
        sku, size, qty, color = rows[0]
        if len(rows) > 1:
            is_combo = True
        else:
            is_combo = qty > 1

        if DEBUG and (DEBUG_PAGE is None or DEBUG_PAGE == i):
            print(f"sku, size, qty -:{sku}, {size}, {qty}")
            print(is_combo)

        # -----------------------------
        # 4️⃣ Bounding box
        # -----------------------------
        bbox = None
        raw = page.get_text("rawdict")
        for block in raw.get("blocks", []):
            if block.get("bbox"):
                r = fitz.Rect(block["bbox"])
                bbox = r if bbox is None else bbox | r

        if not bbox or bbox.is_empty:
            bbox = page.rect

        # -----------------------------
        # 5️⃣ Store page for output
        # -----------------------------
        pages.append({
            "index": i,
            "sku": sku,
            "qty": qty,
            "size": size,
            "color": color,
            "is_combo": is_combo,
            "courier": courier,
            "priority": courier_priority(courier),
            "bbox": bbox,
        })

        courier_counts[courier] += 1

        company = "Unknown"
        for j, ln in enumerate(lines):
            if ln.startswith("If undelivered"):
                if j + 1 < len(lines):
                    company = lines[j + 1]
                break
        company_counts[company] += 1


    pages.sort(
        key=lambda x: (
            x["is_combo"], 
            x["priority"],
            # x["sku"].lower(),   # True first
           (x["sku"] + x["size"] + x["color"]).lower(),
            x["index"],
        )
    )

    # Preserve label order for summary
    summary_order = []
    seen = set()

    for p in pages:
        key = (p["sku"], p["qty"], "")  # size handled below
        if key not in seen:
            summary_order.append(key)
            seen.add(key)



    out = fitz.open()
    usable = fitz.Rect(OUTER_MARGIN, OUTER_MARGIN, LABEL_W - OUTER_MARGIN, LABEL_H - OUTER_MARGIN)
    inner = usable + (INNER_PADDING, INNER_PADDING, -INNER_PADDING, -INNER_PADDING)

    for p in pages:
        src = doc[p["index"]]
        bbox = p["bbox"].intersect(src.rect)
        if bbox.is_empty:
            bbox = src.rect

        scale = min(inner.width / bbox.width, inner.height / bbox.height, 1.0)
        w = bbox.width * scale
        h = bbox.height * scale

        dx = inner.x0 + (inner.width - w) / 2
        dy = inner.y0 + (inner.height - h) / 2
        dest = fitz.Rect(dx, dy, dx + w, dy + h)

        page_out = out.new_page(width=LABEL_W, height=LABEL_H)
        page_out.show_pdf_page(dest, doc, p["index"], clip=bbox)

    
        # 1️⃣ Start from content rectangle
        border_rect = fitz.Rect(
            dest.x0 - BORDER_GAP,
            dest.y0 - BORDER_GAP,
            dest.x1 + BORDER_GAP,
            dest.y1 + BORDER_GAP,
        )

        # 2️⃣ Define safe page boundary
        safe_page_rect = fitz.Rect(
            BORDER_MIN_INSET,
            BORDER_MIN_INSET,
            LABEL_W - BORDER_MIN_INSET,
            LABEL_H - BORDER_MIN_INSET,
        )

        # 3️⃣ Clamp border inside page safely
        border_rect = border_rect & safe_page_rect

        # 4️⃣ Draw border
        page_out.draw_rect(
            border_rect,
            color=(0, 0, 0),
            width=0.6
        )

    # ======================================================
    # SUMMARY
    # ======================================================

    if append_summary:

        # ---- column widths ----
        COL_ORD  = 5
        COL_QTY  = 7
        COL_SIZE = 14
        COL_GAP = 2
        COL_SKU  = 32
        COL_COLOR = 12

        lines = [
            "MEESHO LABEL SUMMARY",
            "Contact: +919426455477 | Powered by ShopSanskriti",
            "",
            f"Generated: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}",
            "",
            f"{'ORD':>{COL_ORD}}"
            f"{'QTY':>{COL_QTY}}"
            f"{'':<{COL_GAP}}"
            f"{'SIZE':<{COL_SIZE}}"
            f"{'COLOR':<{COL_COLOR}}"
            f"{'SKU':<{COL_SKU}}",
            "-" * (COL_ORD + COL_QTY + COL_SIZE + COL_SKU),
        ]

       # ----------------------------------------
        # SUMMARY — COURIER BLOCK BASED
        # ----------------------------------------

        total = 0

        current_courier = None
        courier_ordered_keys = []
        courier_counts_map = defaultdict(int)

        def flush_courier_block():
            nonlocal total, courier_ordered_keys, courier_counts_map

            for (sku, qty, size, color) in courier_ordered_keys:
                ord_cnt = courier_counts_map[(sku, qty, size, color)]

                total += ord_cnt

                lines.append(
                    f"{ord_cnt:>{COL_ORD}}"
                    f"{qty:>{COL_QTY}}"
                    f"{'':<{COL_GAP}}"
                    f"{size:<{COL_SIZE}}"
                    f"{color:<{COL_COLOR}}"
                    f"{fmt_sku(sku, COL_SKU)}"
                )

            # reset for next courier
            courier_ordered_keys = []
            courier_counts_map = defaultdict(int)


        # iterate labels in FINAL label order
        for p in pages:
            courier = p["courier"]

            # detect courier change
            if current_courier is None:
                current_courier = courier
            elif courier != current_courier:
                flush_courier_block()
                current_courier = courier

            page = doc[p["index"]]
            lines_pg = _parse_lines(page)
            rows = extract_product_rows(lines_pg)

            if not rows:
                continue

            for sku, size, qty, color in rows:
                key = (sku, qty, size, color)

                if key not in courier_counts_map:
                    courier_ordered_keys.append(key)

                courier_counts_map[key] += 1


        # flush last courier block
        flush_courier_block()



    lines += [
        "",
        f"Total packages: {total}",
        "",
        "Courier wise:",
    ]

    for c, v in sorted(courier_counts.items()):
        lines.append(f"{v:>5}  {c}")

    lines += [
        "",
        "Company wise:",
    ]

    for company, cnt in sorted(company_counts.items()):
        lines.append(f"{cnt:>5}  {company}")


    font = 6
    margin_x = 8
    margin_y = 10
    line_height = font * 1.4

    p = out.new_page(width=LABEL_W, height=LABEL_H)

    y = margin_y

    for line in lines:
        if y + line_height > LABEL_H - margin_y:
            # start new summary page
            p = out.new_page(width=LABEL_W, height=LABEL_H)
            y = margin_y

        p.insert_text(
            fitz.Point(margin_x, y),
            line,
            fontname="Courier-Bold",   # exact name
            fontsize=font
        )

        y += line_height


    out.save(out_pdf)
    out.close()
    doc.close()

    print(f"✅ Done: {out_pdf} | kept={len(pages)} skipped={skipped}")
    return out_pdf



def fmt_sku(sku, width):
    if len(sku) <= width:
        return sku.ljust(width)
    return sku[:width - 1] + "…"

def extract_product_rows(lines):
    """
    Robust extraction of product rows from Product Details table.
    Does NOT assume order-no count == qty.
    Returns list of (sku, size, qty)
    """
    rows = []
    lines = [l.strip() for l in lines if l.strip()]

    # 1️⃣ Find SKU header
    try:
        header = next(i for i, l in enumerate(lines) if l == "SKU")
    except StopIteration:
        return rows

    # Expected header layout:
    # SKU | Size | Qty | Color | Order No.
    i = header + 5

    while i < len(lines):
        sku = lines[i]

        # End of table
        if sku.upper().startswith(("TAX INVOICE", "BILL TO")):
            break

        # Defensive bounds
        if i + 2 >= len(lines):
            break

        size = lines[i + 1]
        qty_line = lines[i + 2]
        color = lines[i + 3] if i + 3 < len(lines) else ""

        if not qty_line.isdigit():
            break

        qty = int(qty_line)
        rows.append((sku, size, qty, color))

        # 2️⃣ Move pointer forward until NEXT SKU row
        i += 3  # move past sku, size, qty

        while i < len(lines):
            # Stop if next product starts
            if (
                i + 2 < len(lines)
                and lines[i + 2].isdigit()  # Qty position
                and not lines[i].upper().startswith(("TAX INVOICE", "BILL TO"))
            ):
                break

            # Stop if table ends
            if lines[i].upper().startswith(("TAX INVOICE", "BILL TO")):
                return rows

            i += 1

    return rows


# ==========================================================
# FLIPKART HELPERS (UNCHANGED)
# ==========================================================
# ==========================================================
# FLIPKART — CROP TOP INVOICE & FIT LABEL TO PAGE
# ==========================================================
def crop_flipkart_labels(merged_input_pdf: str, output_pdf: str):
    """
    Read merged Flipkart PDF, remove the bottom 'Tax Invoice' part
    and make each cropped label fill a new page with a tiny margin.
    """
    if not os.path.exists(merged_input_pdf):
        print(f"⚠️ Flipkart: file not found: {merged_input_pdf}")
        return

    CUT_ABOVE_TAX = 10  # points above "Tax Invoice" line
    MARGIN = 4          # tiny white border all around (points)

    src = fitz.open(merged_input_pdf)
    out = fitz.open()

    for page_index in range(src.page_count):
        src_page = src.load_page(page_index)
        full_rect = src_page.rect

        # 1) find "Tax Invoice" and decide where to cut
        hits = src_page.search_for("Tax Invoice")
        if hits:
            cut_y = hits[0].y0 - CUT_ABOVE_TAX
        else:
            # if not found, keep whole page
            cut_y = full_rect.y1

        # initial crop region (top part of the page)
        crop_rect = fitz.Rect(full_rect.x0, full_rect.y0, full_rect.x1, cut_y)

        # 2) tighten to actual content inside crop_rect
        bbox = None
        for b in src_page.get_text("blocks"):
            r = fitz.Rect(b[:4])
            if not r.intersects(crop_rect):
                continue
            bbox = r if bbox is None else bbox | r

        # include images as well (barcodes / QR codes)
        for img in src_page.get_images(full=True):
            try:
                r = src_page.get_image_bbox(img[0])
            except Exception:
                r = None
            if not r or not r.intersects(crop_rect):
                continue
            bbox = r if bbox is None else bbox | r

        if bbox is None:
            bbox = crop_rect

        # 3) new page just big enough for content + tiny margin
        width = bbox.width + 2 * MARGIN
        height = bbox.height + 2 * MARGIN
        new_page = out.new_page(width=width, height=height)

        dest_rect = fitz.Rect(
            MARGIN,
            MARGIN,
            width - MARGIN,
            height - MARGIN,
        )

        new_page.show_pdf_page(dest_rect, src, page_index, clip=bbox)

    out.save(output_pdf)
    out.close()
    src.close()
    print(f"✅ Flipkart labels cropped → {output_pdf}")
    return output_pdf


def extract_flipkart_product_rows(lines):
    """
    Extract product rows from Flipkart label.

    Expected table format:
    SKU ID | Description | QTY

    Returns:
    [
        {
            "sku": str,
            "description": str,
            "qty": int,
            "size": str
        }
    ]
    """

    rows = []
    lines = [l.strip() for l in lines if l.strip()]

    # 1️⃣ Find table header
    try:
        header_idx = next(
            i for i, l in enumerate(lines)
            if l.upper().startswith("SKU ID")
        )
    except StopIteration:
        return rows  # no product table found

    i = header_idx + 1

    while i < len(lines):
        line = lines[i]

        # Stop at footer
        if line.lower().startswith(("not for resale", "printed at")):
            break

        # Defensive split
        parts = re.split(r"\s{2,}", line)

        if len(parts) < 2:
            i += 1
            continue

        sku = parts[0].strip()
        desc = parts[1].strip()

        # Qty may be next column or next line
        qty = 1
        if len(parts) >= 3 and parts[-1].isdigit():
            qty = int(parts[-1])
        elif i + 1 < len(lines) and lines[i + 1].isdigit():
            qty = int(lines[i + 1])
            i += 1

        # Best-effort size extraction (e.g. 12-13)
        size_match = re.search(r"\b\d{1,2}\s*-\s*\d{1,2}\b", desc)
        size = size_match.group(0) if size_match else ""

        rows.append({
            "sku": sku,
            "description": desc,
            "qty": qty,
            "size": size,
        })

        i += 1

    return rows

