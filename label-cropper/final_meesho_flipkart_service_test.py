#!/usr/bin/env python3
"""
final_meesho_flipkart_service_test.py

Single-pass label processor (Meesho) with integrated summary generation.
Also includes Flipkart cropping helpers and a simple PDF merge helper.
"""

import os
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import List, Tuple, Optional
from collections import OrderedDict

import fitz      # PyMuPDF
import pandas as pd

# ----------------------------
# Constants & Regexes
# ----------------------------
MM_TO_PT = 72.0 / 25.4
LABEL_W = 100.0 * MM_TO_PT
LABEL_H = 100.0 * MM_TO_PT
OUTER_MARGIN = 0.5 * MM_TO_PT
INNER_PADDING = 0.5 * MM_TO_PT

SKU_FIELD = re.compile(r'\b[a-zA-Z0-9_]+_[a-zA-Z0-9_]+_[a-zA-Z0-9_]+\b')
ORDER_HEADER_RE = re.compile(r'\bOrder\s*No\.?\b', re.IGNORECASE)
SKU_TITLE_RE = re.compile(r'\bSKU\b', re.IGNORECASE)


# ==========================================================
# STEP 0 — MERGE MULTIPLE INPUT FILES
# ==========================================================
def merge_input_pdfs(input_files: List[str], merged_output_path: str) -> str:
    """Merge multiple PDFs into one combined file."""
    merged = fitz.open()
    count = 0
    for pdf_path in input_files:
        if not os.path.exists(pdf_path):
            print(f"⚠️ Skipping missing file: {pdf_path}")
            continue
        try:
            doc = fitz.open(pdf_path)
            merged.insert_pdf(doc)
            doc.close()
            count += 1
        except Exception as e:
            print(f"⚠️ Failed merging {pdf_path}: {e}")
    os.makedirs(os.path.dirname(merged_output_path) or ".", exist_ok=True)
    merged.save(merged_output_path)
    merged.close()
    print(f"✅ Merged {count} PDFs → {merged_output_path}")
    return merged_output_path


# ==========================================================
# HELPERS (text parsing & extraction)
# ==========================================================
def _parse_lines_from_rawdict(raw: dict) -> List[str]:
    """Return ordered text lines from rawdict (fast & stable)."""
    lines = []
    for block in raw.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            spans = [span.get("text", "").strip() for span in line.get("spans", []) if span.get("text", "").strip()]
            if spans:
                lines.append(" ".join(spans))
    return lines


def extract_items_from_label_lines(lines: List[str]) -> List[Tuple[str, str, str, str, str]]:
    """
    Extract product rows from lines following an 'Order No.' header.
    Returns list of tuples: (sku, size, qty, color, order_no)
    Keeps the original logic but works on the passed slice of lines.
    """
    items = []
    lines = [l.strip() for l in lines if l.strip()]
    # locate header
    try:
        idx = next(i for i, l in enumerate(lines) if ORDER_HEADER_RE.search(l))
    except StopIteration:
        return items

    j = idx + 1
    while j + 4 < len(lines):
        sku = lines[j].strip()
        size = lines[j + 1].strip()
        qty = lines[j + 2].strip()
        color = lines[j + 3].strip()
        order = lines[j + 4].strip()

        if sku in ("TAX INVOICE", "BILL TO / SHIP TO", "Description"):
            break
        if not re.search(r'\d+', qty):
            break

        items.append((sku, size, qty, color, order))
        j += 5

    return items


def extract_courier(lines: List[str]) -> str:
    """
    Heuristic courier detection using 'pickup' token and normalization.
    """
    def normalize_courier(raw_name: str) -> str:
        if not raw_name:
            return "Unknown"
        low = raw_name.lower()
        if re.search(r"\bvalmo", low): return "Valmo"
        if re.search(r"\bxpress", low): return "Xpressbees"
        if re.search(r"\bdelhivery", low): return "Delhivery"
        if re.search(r"\bekart", low): return "Ekart"
        if re.search(r"\bshadowfax", low): return "Shadowfax"
        if re.search(r"\becom\s*express", low): return "Ecom Express"
        return raw_name.strip()

    for i, ln in enumerate(lines):
        low = ln.lower()
        if re.search(r'\bpickup\b', low):
            if re.search(r'\bvalmo', low):
                return "Valmo"
            # look backward for courier line
            j = i - 1
            while j >= 0:
                prev = lines[j].strip()
                if prev:
                    return normalize_courier(prev)
                j -= 1
            return normalize_courier(ln.strip())
    return "Unknown"


# ==========================================================
# STEP 1 (SINGLE-PASS) — PROCESS, SORT, CROP & SUMMARY
# ==========================================================
def process_labels_single_pass(input_pdf: str,
                               sku_mapping_csv: Optional[str],
                               out_pdf: str,
                               append_summary: bool = True) -> str:
    """
    Single-pass:
      - opens input_pdf once
      - for each page: extracts lines, SKU, qty, bbox, courier/company
      - SKIPS pages that have no SKU-like token
      - collects summary info while scanning
      - creates final LABEL_W x LABEL_H pages in sorted order
      - appends summary pages (if append_summary=True) BEFORE saving
    Returns out_pdf path.
    """
    if not os.path.exists(input_pdf):
        raise FileNotFoundError(f"input pdf not found: {input_pdf}")

    # Load SKU mapping if present
    child_to_parent = {}
    if sku_mapping_csv and os.path.exists(sku_mapping_csv):
        try:
            df = pd.read_csv(sku_mapping_csv)
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            if {'parent_sku', 'child_sku'}.issubset(df.columns):
                child_to_parent = dict(zip(df['child_sku'], df['parent_sku']))
        except Exception as e:
            print(f"⚠️ Warning: failed to load SKU mapping: {e}")

    doc = fitz.open(input_pdf)
    N = doc.page_count

    pages_meta = []                   # kept pages metadata
    skipped_count = 0

    # summary aggregators
    sku_groups = defaultdict(list)    # (sku, size, qty) -> [order_no, ...]
    courier_counts = defaultdict(int)
    company_counts = defaultdict(int)

    for i in range(N):
        page = doc[i]
        raw = page.get_text("rawdict")
        lines = _parse_lines_from_rawdict(raw)

        # fallback to plain text if rawdict empty
        if not lines:
            txt = page.get_text("text") or ""
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]

        # try to extract SKU & qty using lines
        sku = None
        qty = None
        # scan for header-based rows
        items = []
        try:
            # using extract_items_from_label_lines on the entire page to detect table rows
            items = extract_items_from_label_lines(lines)
            if items:
                # if we have rows, pick first row's sku and qty for metadata
                first = items[0]
                sku = first[0]
                qty = int(re.search(r'(\d+)', first[2]).group(1)) if re.search(r'(\d+)', first[2]) else 1
        except Exception:
            items = []

        # liberal scan for sku tokens if header parsing fails
        txt_concat = " ".join(lines)
        skus_all = SKU_FIELD.findall(txt_concat)

        if not skus_all and sku is None:
            # nothing looks like SKU -> skip this page
            skipped_count += 1
            continue

        if sku is None and skus_all:
            sku = skus_all[0]

        if qty is None:
            # try to find qty number near SKU or anywhere on page
            m = re.search(r'\bQty[:\s]*([0-9]+)\b', txt_concat, re.IGNORECASE)
            if m:
                qty = int(m.group(1))
            else:
                m2 = re.search(r'(\d+)', txt_concat)
                qty = int(m2.group(1)) if m2 else 1

        # compute bbox from textual spans and image blocks
        bbox = None
        for block in raw.get("blocks", []):
            if block.get("type", 0) == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        b = span.get("bbox")
                        if b:
                            r = fitz.Rect(b)
                            bbox = r if bbox is None else bbox | r
            elif block.get("type", 1):
                b = block.get("bbox")
                if b:
                    r = fitz.Rect(b)
                    bbox = r if bbox is None else bbox | r

        if bbox is None or bbox.is_empty:
            bbox = page.rect

        # is_combo determination
        is_combo = (len(skus_all) > 1) or (qty and int(qty) > 1)

        parent = child_to_parent.get(sku, sku)

        pages_meta.append({
            "index": i,
            "parent": parent,
            "sku": sku,
            "qty": int(qty),
            "is_combo": is_combo,
            "bbox": bbox,
            "lines": lines,
            "items": items,   # parsed rows (may be empty if we picked sku by token)
        })

        # --- accumulate summary info from this page (if items found)
        if items:
            for (s, size, q_raw, color, order_no) in items:
                qm = re.search(r'(\d+)', q_raw)
                qv = int(qm.group(1)) if qm else 1
                sku_groups[(s, size, qv)].append(order_no or "")
        else:
            # If no structured rows, attempt a fallback summary extraction:
            # use parsed sku, qty, and try to find an order number in nearby lines
            order_no = ""
            for ln in lines:
                # Order numbers commonly numeric/alphanumeric; pick first long-ish token
                m = re.search(r'\b([A-Za-z0-9\-]{4,})\b', ln)
                if m and not ORDER_HEADER_RE.search(ln):
                    order_no = m.group(1)
                    break
            sku_groups[(sku, "", int(qty))].append(order_no)

        # courier & company heuristics
        courier = extract_courier(lines)
        courier_counts[courier] += 1

        company = "Unknown"
        for j, ln in enumerate(lines):
            if ln.strip().startswith("If undelivered, return to"):
                for k in range(j + 1, len(lines)):
                    if lines[k].strip():
                        company = lines[k].strip()
                        break
                break
        company_counts[company] += 1

    if not pages_meta:
        doc.close()
        raise RuntimeError("No label pages with SKU found in input PDF (all pages skipped).")

    # Sort pages: singles first (not combo), then by parent_sku, then child sku
    sorted_meta = sorted(pages_meta, key=lambda x: (not x["is_combo"], x["parent"].lower(), x["sku"].lower()))


    # parent_buckets = OrderedDict()  # preserves first-seen parent order
    # for m in pages_meta:
    #     parent = m["parent"]
    #     if parent not in parent_buckets:
    #         parent_buckets[parent] = {"singles": [], "combos": []}
    #     if m["is_combo"]:
    #         parent_buckets[parent]["combos"].append(m)
    #     else:
    #         parent_buckets[parent]["singles"].append(m)

    # # Build sorted_meta by iterating buckets (parents in first-seen order)
    # sorted_meta = []
    # for parent, groups in parent_buckets.items():
    #     # append singles first, then combos (keeps original page order inside each list)
    #     sorted_meta.extend(groups["singles"])
    #     sorted_meta.extend(groups["combos"])
    # === end grouping ===


    # Build final output doc
    out_doc = fitz.open()
    usable = fitz.Rect(OUTER_MARGIN, OUTER_MARGIN, LABEL_W - OUTER_MARGIN, LABEL_H - OUTER_MARGIN)
    inner = fitz.Rect(usable.x0 + INNER_PADDING, usable.y0 + INNER_PADDING, usable.x1 - INNER_PADDING, usable.y1 - INNER_PADDING)

    for m in sorted_meta:
        idx = m["index"]
        bbox = m["bbox"].intersect(doc[idx].rect)
        if bbox.is_empty:
            bbox = doc[idx].rect

        content_w, content_h = bbox.width, bbox.height
        if content_w <= 0 or content_h <= 0:
            scale = 1.0
        else:
            scale = min(inner.width / content_w, inner.height / content_h, 1.0)

        scaled_w = content_w * scale
        scaled_h = content_h * scale
        dx = inner.x0 + (inner.width - scaled_w) / 2
        dy = inner.y0 + (inner.height - scaled_h) / 2
        dest = fitz.Rect(dx, dy, dx + scaled_w, dy + scaled_h)

        new_page = out_doc.new_page(width=LABEL_W, height=LABEL_H)
        new_page.show_pdf_page(dest, doc, idx, clip=bbox)

        # ADD THIS 👇
        border_margin = OUTER_MARGIN / 2
        border_rect = fitz.Rect(
            border_margin,
            border_margin,
            LABEL_W - border_margin,
            LABEL_H - border_margin
        )
        new_page.draw_rect(border_rect, color=(0, 0, 0), width=1.0)

    # Append summary pages (built from sku_groups, courier_counts, company_counts)
    if append_summary and sku_groups:
        lines_out = []
        lines_out.append("LABEL SUMMARY")
        lines_out.append("")
        lines_out.append(f"Generated: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}")
        lines_out.append("")
        header = f"{'ORD':>5} {'QTY':>5} {'Size':<15} {'SKU'}"
        lines_out.append(header)
        lines_out.append("-" * len(header))

        total_packages = 0
        for (sku, size, qty), orders in sorted(sku_groups.items(), key=lambda x: (x[0][0].lower(), x[0][1].lower())):
            ord_count = len(orders)
            total_packages += ord_count
            lines_out.append(f"{ord_count:>5} {qty:>5} {size[:14]:<15} {sku}")

        lines_out.append("")
        lines_out.append(f"Total package: {total_packages}")
        lines_out.append("")
        lines_out.append("Courier wise total package:")
        lines_out.append(f"{'Package':>7}  Courier Partner")
        for courier, cnt in sorted(courier_counts.items(), key=lambda x: x[0].lower()):
            lines_out.append(f"{cnt:>7}  {courier}")
        lines_out.append("")
        lines_out.append("Company wise total package:")
        lines_out.append(f"{'Package':>7}  Sold By")
        for company, cnt in sorted(company_counts.items(), key=lambda x: x[0].lower()):
            lines_out.append(f"{cnt:>7}  {company}")

        # write lines_out into multiple label-sized pages
        font_size = 7
        margin = 8
        usable_height = LABEL_H - 2 * margin
        line_h = font_size * 1.3
        max_lines = max(5, int(usable_height // line_h))

        for start in range(0, len(lines_out), max_lines):
            chunk = lines_out[start:start + max_lines]
            p = out_doc.new_page(width=LABEL_W, height=LABEL_H)
            rect = fitz.Rect(margin, margin, LABEL_W - margin, LABEL_H - margin)
            p.insert_textbox(rect, "\n".join(chunk), fontname="courier", fontsize=font_size, align=0)

    # Save final output
    os.makedirs(os.path.dirname(out_pdf) or ".", exist_ok=True)
    out_doc.save(out_pdf)
    out_doc.close()
    doc.close()

    print(f"✅ Final labels saved: {out_pdf} ({len(sorted_meta)} pages kept, {skipped_count} pages skipped, summary_pages_added={(len(lines_out) + max_lines - 1)//max_lines if append_summary and sku_groups else 0})")
    return out_pdf


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

        hits = src_page.search_for("Tax Invoice")
        if hits:
            cut_y = hits[0].y0 - CUT_ABOVE_TAX
        else:
            cut_y = full_rect.y1

        crop_rect = fitz.Rect(full_rect.x0, full_rect.y0, full_rect.x1, cut_y)

        bbox = None
        raw = src_page.get_text("rawdict")
        for block in raw.get("blocks", []):
            if block.get("type", 0) == 0:
                r = None
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("bbox"):
                            r = fitz.Rect(span.get("bbox"))
                            break
                    if r:
                        break
                if r and r.intersects(crop_rect):
                    bbox = r if bbox is None else bbox | r
            elif block.get("type", 1):
                b = block.get("bbox")
                if b:
                    r = fitz.Rect(b)
                    if r.intersects(crop_rect):
                        bbox = r if bbox is None else bbox | r

        if bbox is None:
            bbox = crop_rect

        width = bbox.width + 2 * MARGIN
        height = bbox.height + 2 * MARGIN
        new_page = out.new_page(width=width, height=height)
        dest_rect = fitz.Rect(MARGIN, MARGIN, width - MARGIN, height - MARGIN)
        new_page.show_pdf_page(dest_rect, src, page_index, clip=bbox)

    out.save(output_pdf)
    out.close()
    src.close()
    print(f"✅ Flipkart labels cropped → {output_pdf}")
    return output_pdf


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
# Compatibility wrappers (clear errors to guide migration)
# ==========================================================
def sort_pdf_by_parent_sku(*args, **kwargs):
    raise NotImplementedError("sort_pdf_by_parent_sku is deprecated; use process_labels_single_pass instead.")

def crop_and_fit_labels(*args, **kwargs):
    raise NotImplementedError("crop_and_fit_labels is deprecated; use process_labels_single_pass instead.")

def append_summary_page(*args, **kwargs):
    raise NotImplementedError("append_summary_page is deprecated; use process_labels_single_pass(..., append_summary=True).")
