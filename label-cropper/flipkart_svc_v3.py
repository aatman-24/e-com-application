#!/usr/bin/env python3
"""
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
BORDER_GAP = 4 
BORDER_MIN_INSET = 1


SKU_FIELD = re.compile(r'\b[a-zA-Z0-9_]+_[a-zA-Z0-9_]+_[a-zA-Z0-9_]+\b')
ORDER_HEADER_RE = re.compile(r'\bOrder\s*No\.?\b', re.IGNORECASE)


DEBUG = True
DEBUG_PAGE = 6   # set to page number later (0-based)


def process_flipkart_single_pass(
    input_pdf: str,
    out_pdf: str,
    append_summary: bool = True,
):
    doc = fitz.open(input_pdf)
    out = fitz.open()

    pages = []
    courier_counts = defaultdict(int)
    company_counts = defaultdict(int)
    seller_counts = defaultdict(int)  # alias of company, but named clearer

    sku_groups = defaultdict(int)

    for i in range(doc.page_count):
        page = doc[i]
        lines = _parse_lines(page)

        courier, company = extract_flipkart_courier_and_company(lines)

        # 🔽 INCREMENT COUNTS (ONCE PER PAGE)
        courier_counts[courier] += 1
        company_counts[company] += 1
        seller_counts[company] += 1

        # -----------------------------
        # 1️⃣ Extract product rows (Flipkart)
        # -----------------------------
        rows = extract_flipkart_product_rows(lines)
        if not rows:
            continue

        # -----------------------------
        # 2️⃣ Page metadata (first row)
        # -----------------------------
        sku, size, qty, color = rows[0]
        is_combo = len(rows) > 1 or qty > 1

        # -----------------------------
        # 3️⃣ Summary aggregation
        # -----------------------------
        for sku, size, qty, color in rows:
            sku_groups[(sku, size, color, qty)] += 1

        # -----------------------------
        # 4️⃣ Flipkart crop bbox
        # -----------------------------
        hits = page.search_for("Tax Invoice")
        cut_y = hits[0].y0 if hits else page.rect.y1
        bbox = fitz.Rect(
            page.rect.x0,
            page.rect.y0,
            page.rect.x1,
            cut_y
        )

        pages.append({
            "index": i,
            "sku": sku,
            "size": size,
            "color": color,
            "qty": qty,
            "is_combo": is_combo,
            "courier": courier,     # 👈 NEW
            "company": company,     # 👈 NEW
            "bbox": bbox,
        })

    # -----------------------------
    # 5️⃣ SORT (simple, predictable)
    # -----------------------------
    pages.sort(
        key=lambda x: (
            x["is_combo"],
            (x["sku"] + x["size"] + x["color"]).lower(),
            x["index"],
        )
    )

    # -----------------------------
    # 6️⃣ RENDER LABELS + BORDER
    # -----------------------------
    usable = fitz.Rect(
        OUTER_MARGIN,
        OUTER_MARGIN,
        LABEL_W - OUTER_MARGIN,
        LABEL_H - OUTER_MARGIN
    )

    for p in pages:
        src = doc[p["index"]]
        bbox = p["bbox"]

        scale = min(
            usable.width / bbox.width,
            usable.height / bbox.height,
            1.0
        )

        w = bbox.width * scale
        h = bbox.height * scale

        dx = usable.x0 + (usable.width - w) / 2
        dy = usable.y0 + (usable.height - h) / 2

        dest = fitz.Rect(dx, dy, dx + w, dy + h)

        page_out = out.new_page(width=LABEL_W, height=LABEL_H)
        page_out.show_pdf_page(dest, doc, p["index"], clip=bbox)

        border_rect = fitz.Rect(
            dest.x0 - BORDER_GAP,
            dest.y0 - BORDER_GAP,
            dest.x1 + BORDER_GAP,
            dest.y1 + BORDER_GAP,
        )

        page_out.draw_rect(border_rect, width=0.6)

    summary_order = []
    seen = set()

    for p in pages:  # pages is already SORTED for rendering
        key = (p["sku"], p["size"], p["color"], p["qty"])
        if key not in seen:
            summary_order.append(key)
            seen.add(key)

    # -----------------------------
    # 7️⃣ SUMMARY (simple version)
    # -----------------------------
    if append_summary:
        _append_simple_summary(out, sku_groups, summary_order, courier_counts, company_counts)

    out.save(out_pdf)
    out.close()
    doc.close()

    return out_pdf

def _append_simple_summary(out, sku_groups, summary_order, courier_counts, company_counts):
    font = 6
    margin = 8

    COL_ORD = 5
    COL_QTY = 7
    COL_SKU = 40   # wider, since SKU includes description
    
    total = 0

    lines = [
        "FLIPKART LABEL SUMMARY",
        "Contact: +919426455477 | Powered by ShopSanskriti",
        "",
        f"Generated: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}",
        "",
        f"{'ORD':>{COL_ORD}}"
        f"{'QTY':>{COL_QTY}}  "
        f"{'SKU':<{COL_SKU}}",
        "-" * (COL_ORD + COL_QTY + COL_SKU),
    ]

    for (sku, size, color, qty) in summary_order:
        cnt = sku_groups.get((sku, size, color, qty), 0)
        if cnt <= 0:
            continue

        total += cnt

        lines.append(
            f"{cnt:>{COL_ORD}}"
            f"{qty:>{COL_QTY}}  "
            f"{fmt_sku(sku, COL_SKU)}"
        )

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


    font = 7
    fontname = "Courier-Bold"
    margin_x = 8
    margin_y = 10
    line_height = font * 1.4

    # create first summary page
    page = out.new_page(width=LABEL_W, height=LABEL_H)
    y = margin_y

    for line in lines:
        # 🚨 BEFORE drawing, check boundary
        if y + line_height > LABEL_H - margin_y:
            # start new page BEFORE overflow
            page = out.new_page(width=LABEL_W, height=LABEL_H)
            y = margin_y

        page.insert_text(
            fitz.Point(margin_x, y),
            line,
            fontsize=font,
            fontname=fontname
        )

        y += line_height


def fmt_sku(sku, width):
    if len(sku) <= width:
        return sku.ljust(width)
    return sku[:width - 1] + "…"   


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


def extract_flipkart_product_rows(lines):
    """
    Extract Flipkart product rows from parsed lines.

    Real pattern:
    - SKU line starts with index (ignore it)
    - Description may span multiple lines
    - Quantity is a standalone digit line AFTER description

    Returns:
    list of (sku, size, qty, color)
    """

    rows = []
    lines = [l.strip() for l in lines if l.strip()]

    # 1️⃣ Find SKU table header
    try:
        start = next(
            i for i, l in enumerate(lines)
            if l.upper() == "SKU ID | DESCRIPTION"
        )
    except StopIteration:
        return rows

    i = start + 1

    # Skip until QTY header
    while i < len(lines) and lines[i].upper() != "QTY":
        i += 1
    i += 1  # move past QTY

    # 2️⃣ Parse SKU blocks
    while i < len(lines):
        line = lines[i]

        if line.lower().startswith((
            "tax",
            "invoice",
            "order id",
            "not for resale",
            "printed at",
            "sold by",
            "shipping",
            "customer",
            "name:",
            "gstin",
            "fmp",
        )):
            break

        # SKU line must start with an index number
        m = re.match(r"\d+\s+(.+)", line)
        if not m:
            i += 1
            continue

        # First description line (ignore index)
        desc_lines = [m.group(1)]

        # desc_lines = [_strip_flipkart_index(m.group(1))]
        j = i + 1

        # Collect continuation description lines
        while j < len(lines):
            # Quantity line → end of description block
            if lines[j].isdigit():
                break

            # Hard stop markers
            if lines[j].lower().startswith((
                "tax",
                "invoice",
                "order id"
            )):
                break

            desc_lines.append(lines[j])
            # todo: 
            # desc_lines.append(_strip_flipkart_index(lines[j])) 
            j += 1

        # Quantity (standalone digit line)
        qty = int(lines[j]) if j < len(lines) and lines[j].isdigit() else 1

        full_desc = " ".join(desc_lines)

        # SKU = everything before '|', if present
        sku = full_desc.split("|")[0].strip()

        # Extract size (e.g. 4-5, 12-13)
        size_match = re.search(r"\b\d{1,2}\s*-\s*\d{1,2}\b", full_desc)
        size = size_match.group(0) if size_match else ""

        color = ""  # Flipkart color unreliable

        rows.append((sku, size, qty, color))

        # Move pointer past qty and any trailing junk (like FMPP code)
        i = j + 1
        # while i < len(lines) and not re.match(r"\d+\s+.+", lines[i]):
            # i += 1

    return rows

def extract_flipkart_courier_and_company(lines):
    """
    Returns (courier, company)
    """

    courier = "Unknown"
    company = "Unknown"

    for ln in lines:
        low = ln.lower()

        # Courier
        if "logistics" in low or "ekart" in low:
            courier = ln.strip()

        # Company
        if low.startswith("sold by:"):
            company = ln.split(":", 1)[1].strip()
            # remove trailing address comma
            if "," in company:
                company = company.split(",", 1)[0].strip()

    return courier, company



############# NEW CODE ######################

LABEL_4X6_W = 100.0 * MM_TO_PT
LABEL_4X6_H = 150.0 * MM_TO_PT
BORDER_GAP_4_6 = 8

def process_flipkart_single_pass_4x6(
    input_pdf: str,
    out_pdf: str,
    append_summary: bool = True,
):
    """
    4x6 inch version of Flipkart label processor.
    NOTE:
    - This function intentionally DUPLICATES logic
    - Existing 4x4 code remains untouched
    """

    LABEL_W_4X6 = 100.0 * MM_TO_PT   # 4 inch
    LABEL_H_4X6 = 150.0 * MM_TO_PT   # 6 inch

    doc = fitz.open(input_pdf)
    out = fitz.open()

    pages = []
    courier_counts = defaultdict(int)
    company_counts = defaultdict(int)
    sku_groups = defaultdict(int)

    for i in range(doc.page_count):
        page = doc[i]
        lines = _parse_lines(page)

        courier, company = extract_flipkart_courier_and_company(lines)

        courier_counts[courier] += 1
        company_counts[company] += 1

        rows = extract_flipkart_product_rows(lines)
        if not rows:
            continue

        sku, size, qty, color = rows[0]
        is_combo = len(rows) > 1 or qty > 1

        for sku, size, qty, color in rows:
            sku_groups[(sku, size, color, qty)] += 1

        hits = page.search_for("Tax Invoice")
        cut_y = hits[0].y0 if hits else page.rect.y1
        bbox = fitz.Rect(
            page.rect.x0,
            page.rect.y0,
            page.rect.x1,
            cut_y
        )

        pages.append({
            "index": i,
            "sku": sku,
            "size": size,
            "color": color,
            "qty": qty,
            "is_combo": is_combo,
            "courier": courier,
            "company": company,
            "bbox": bbox,
        })

    pages.sort(
        key=lambda x: (
            x["is_combo"],
            (x["sku"] + x["size"] + x["color"]).lower(),
            x["index"],
        )
    )

    page_rect = fitz.Rect(0, 0, LABEL_W_4X6, LABEL_H_4X6)
    
    for p in pages:
        bbox = p["bbox"]

        scale = min(
            page_rect.width / bbox.width,
            page_rect.height / bbox.height
        )

        w = bbox.width * scale
        h = bbox.height * scale

        dx = (page_rect.width - w) / 2
        dy = (page_rect.height - h) / 2

        dest = fitz.Rect(dx, dy, dx + w, dy + h)

        page_out = out.new_page(
            width=LABEL_W_4X6,
            height=LABEL_H_4X6
        )

        page_out.show_pdf_page(dest, doc, p["index"], clip=bbox)

        border_rect = fitz.Rect(
            dest.x0 - BORDER_GAP_4_6,
            dest.y0 - BORDER_GAP_4_6,
            dest.x1 + BORDER_GAP_4_6,
            dest.y1 + BORDER_GAP_4_6,
        )

        page_out.draw_rect(border_rect, width=0.6)

    # added by me 
    summary_order = []
    seen = set()

    for p in pages:  # pages is already SORTED for rendering
        key = (p["sku"], p["size"], p["color"], p["qty"])
        if key not in seen:
            summary_order.append(key)
            seen.add(key)

    if append_summary:
        _append_simple_summary_4x6(
            out,
            sku_groups,
            summary_order,
            courier_counts,
            company_counts
        )

    out.save(out_pdf)
    out.close()
    doc.close()

    return out_pdf


def _append_simple_summary_4x6(
    out,
    sku_groups,
    summary_order,
    courier_counts,
    company_counts,
):
    font = 7
    margin_x = 10
    margin_y = 12
    line_height = font * 1.4

    COL_ORD = 5
    COL_QTY = 7
    COL_SKU = 50   # wider for 4x6

    total = 0

    lines = [
        "FLIPKART LABEL SUMMARY",
        "Contact: +919426455477 | Powered by ShopSanskriti",
        "",
        f"Generated: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}",
        "",
        f"{'ORD':>{COL_ORD}}"
        f"{'QTY':>{COL_QTY}}  "
        f"{'SKU':<{COL_SKU}}",
        "-" * (COL_ORD + COL_QTY + COL_SKU),
    ]

    for (sku, size, color, qty) in summary_order:
        cnt = sku_groups.get((sku, size, color, qty), 0)
        if cnt <= 0:
            continue

        total += cnt
        lines.append(
            f"{cnt:>{COL_ORD}}"
            f"{qty:>{COL_QTY}}  "
            f"{fmt_sku(sku, COL_SKU)}"
        )

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

    page = out.new_page(width=LABEL_4X6_W, height=LABEL_4X6_H)
    y = margin_y

    for line in lines:
        if y + line_height > LABEL_4X6_H - margin_y:
            page = out.new_page(width=LABEL_4X6_W, height=LABEL_4X6_H)
            y = margin_y

        page.insert_text(
            fitz.Point(margin_x, y),
            line,
            fontsize=font,
            fontname="Courier-Bold"
        )
        y += line_height


# def _strip_flipkart_index(text: str) -> str:
#     """
#     Removes leading numeric order index from Flipkart SKU lines.
#     Examples:
#     - '1BLUE M TSHURT' → 'BLUE M TSHURT'
#     - '11141* - Black + Pink' → '1141* - Black + Pink' ❌ (wrong, so we avoid this)
#     """

#     return re.sub(r"^\d+(?=[A-Za-z*])", "", text).strip()


def _strip_flipkart_index(text: str) -> str:
    """
    Removes the first character (order index) from Flipkart SKU lines.
    """
    return text[1:].lstrip() if text else text

