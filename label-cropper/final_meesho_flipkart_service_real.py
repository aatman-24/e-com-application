#!/usr/bin/env python3
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

OUTER_MARGIN = 0.3 * MM_TO_PT
BORDER_GAP = 4
BORDER_MIN_INSET = 1

# Flipkart label sizes (mm)
FLIPKART_LABEL_SIZES_MM = {
    "4x4": (100.0, 100.0),
    "4x6": (100.0, 150.0),
}

def mm_to_pt(mm):
    return mm * MM_TO_PT


# ==========================================================
# MAIN FLIPKART PIPELINE
# ==========================================================
def process_flipkart_single_pass(
    input_pdf: str,
    out_pdf: str,
    label_size: str = "4x4",
    append_summary: bool = True,
):
    doc = fitz.open(input_pdf)
    out = fitz.open()

    pages = []
    sku_groups = defaultdict(int)
    courier_counts = defaultdict(int)
    company_counts = defaultdict(int)

    label_w_mm, label_h_mm = FLIPKART_LABEL_SIZES_MM[label_size]
    LABEL_W = mm_to_pt(label_w_mm)
    LABEL_H = mm_to_pt(label_h_mm)

    for i in range(doc.page_count):
        page = doc[i]
        lines = _parse_lines(page)

        rows = extract_flipkart_product_rows(lines)
        if not rows:
            continue  # ❗ count ONLY valid labels

        courier, company = extract_flipkart_courier_and_company(lines)

        courier_counts[courier] += 1
        company_counts[company] += 1

        sku, size, qty, color = rows[0]
        is_combo = len(rows) > 1 or qty > 1

        for sku, size, qty, color in rows:
            sku_groups[(sku, size, color, qty)] += 1

        # --- tight crop ---
        hits = page.search_for("Tax Invoice")
        cut_y = hits[0].y0 if hits else page.rect.y1

        bbox = None
        for b in page.get_text("blocks"):
            r = fitz.Rect(b[:4])
            if r.y1 <= cut_y:
                bbox = r if bbox is None else bbox | r

        if bbox is None:
            bbox = fitz.Rect(page.rect.x0, page.rect.y0, page.rect.x1, cut_y)

        pages.append({
            "index": i,
            "sku": sku,
            "size": size,
            "color": color,
            "qty": qty,
            "is_combo": is_combo,
            "bbox": bbox,
        })

    pages.sort(key=lambda x: (x["is_combo"], (x["sku"] + x["size"]).lower()))

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

        border = dest + (-BORDER_GAP, -BORDER_GAP, BORDER_GAP, BORDER_GAP)
        safe = fitz.Rect(
            BORDER_MIN_INSET,
            BORDER_MIN_INSET,
            LABEL_W - BORDER_MIN_INSET,
            LABEL_H - BORDER_MIN_INSET,
        )

        page_out.draw_rect(border & safe, width=0.6)

    summary_order = []
    seen = set()
    for p in pages:
        key = (p["sku"], p["size"], p["color"], p["qty"])
        if key not in seen:
            summary_order.append(key)
            seen.add(key)

    if append_summary:
        _append_simple_summary(
            out,
            sku_groups,
            summary_order,
            courier_counts,
            company_counts,
            LABEL_W,
            LABEL_H
        )

    out.save(out_pdf)
    out.close()
    doc.close()
    return out_pdf


# ==========================================================
# SUMMARY (SAFE, PAGINATED)
# ==========================================================
def _append_simple_summary(
    out,
    sku_groups,
    summary_order,
    courier_counts,
    company_counts,
    LABEL_W,
    LABEL_H
):
    font = 8
    line_h = font * 1.4
    x = 8
    y0 = 10

    lines = [
        "FLIPKART LABEL SUMMARY",
        "",
        f"Generated: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}",
        "",
        "ORD   QTY   SKU",
        "-" * 50,
    ]

    total = 0
    for k in summary_order:
        cnt = sku_groups[k]
        total += cnt
        sku, _, _, qty = k
        lines.append(f"{cnt:>3}   {qty:>3}   {sku}")

    lines += [
        "",
        f"Total packages: {total}",
        "",
        "Courier wise:",
    ]

    for c, v in courier_counts.items():
        lines.append(f"{v:>5}  {c}")

    lines += [
        "",
        "Company wise:",
    ]

    for c, v in company_counts.items():
        lines.append(f"{v:>5}  {c}")

    page = out.new_page(width=LABEL_W, height=LABEL_H)
    y = y0

    for ln in lines:
        if y + line_h > LABEL_H - y0:
            page = out.new_page(width=LABEL_W, height=LABEL_H)
            y = y0

        page.insert_text(
            fitz.Point(x, y),
            ln,
            fontsize=font,
            fontname="Courier-Bold"
        )
        y += line_h


# ==========================================================
# HELPERS (unchanged logic)
# ==========================================================
def fmt_sku(sku, width):
    return sku if len(sku) <= width else sku[:width - 1] + "…"


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
    return lines


def extract_flipkart_courier_and_company(lines):
    courier = "Unknown"
    company = "Unknown"
    for ln in lines:
        low = ln.lower()
        if "logistics" in low or "ekart" in low:
            courier = ln.strip()
        if low.startswith("sold by:"):
            company = ln.split(":", 1)[1].split(",")[0].strip()
    return courier, company


def extract_flipkart_product_rows(lines):
    rows = []
    try:
        start = next(i for i, l in enumerate(lines) if l.upper() == "SKU ID | DESCRIPTION")
    except StopIteration:
        return rows

    i = start + 1
    while i < len(lines) and lines[i].upper() != "QTY":
        i += 1
    i += 1

    while i < len(lines):
        if lines[i].isdigit():
            break

        m = re.match(r"\d+\s+(.+)", lines[i])
        if not m:
            i += 1
            continue

        desc = m.group(1)
        qty = int(lines[i + 1]) if i + 1 < len(lines) and lines[i + 1].isdigit() else 1
        sku = desc.split("|")[0].strip()

        rows.append((sku, "", qty, ""))
        i += 2

    return rows
