#!/usr/bin/env python3
# Service module: final_meesho_flipkart_service_test.py
# Provides: merge_input_pdfs, process_labels_single_pass, process_flipkart_labels, crop_flipkart_labels

import os
import re
import fitz    # PyMuPDF
import pandas as pd
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import List, Tuple, Optional

# ----------------------------
# Basic helpers & constants
# ----------------------------
MM_TO_PT = 72.0 / 25.4
LABEL_W = 100.0 * MM_TO_PT
LABEL_H = 100.0 * MM_TO_PT
OUTER_MARGIN = 0.5 * MM_TO_PT
INNER_PADDING = 0.5 * MM_TO_PT

SKU_FIELD = re.compile(r'\b[a-zA-Z0-9_]+_[a-zA-Z0-9_]+_[a-zA-Z0-9_]+\b')
ORDER_HEADER = re.compile(r'\bOrder No\.?\b', re.IGNORECASE)
SKU_TITLE = re.compile(r'\bSKU\b', re.IGNORECASE)


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
        doc = fitz.open(pdf_path)
        merged.insert_pdf(doc)
        count += 1
    os.makedirs(os.path.dirname(merged_output_path) or ".", exist_ok=True)
    merged.save(merged_output_path)
    merged.close()
    print(f"✅ Merged {count} PDFs → {merged_output_path}")
    return merged_output_path


# ==========================================================
# SINGLE-PASS PROCESSOR (extract -> sort -> crop -> summary)
# ==========================================================
def _parse_lines_from_rawdict(raw: dict) -> List[str]:
    """Return ordered text lines from rawdict (fast)."""
    lines = []
    for block in raw.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            spans = [span.get("text", "").strip() for span in line.get("spans", []) if span.get("text", "").strip()]
            if spans:
                lines.append(" ".join(spans))
    return lines


def _find_sku_qty_from_lines(lines: List[str]) -> Tuple[Optional[str], Optional[int]]:
    """Attempt to extract sku & qty from lines (table under Order No.)."""
    for i, ln in enumerate(lines):
        if ORDER_HEADER.search(ln):
            # typical layout: next lines contain sku, size, qty, color, orderno
            if i + 3 < len(lines):
                cand_line = lines[i + 1].strip()
                cand_sku = cand_line.split()[0] if cand_line.split() else None
                cand_qty = None
                for j in range(i + 1, min(i + 8, len(lines))):
                    m = re.search(r'(\d+)', lines[j])
                    if m:
                        cand_qty = int(m.group(1))
                        break
                if cand_sku and SKU_FIELD.match(cand_sku):
                    return cand_sku, (cand_qty or 1)
    # liberal fallback: scan tokens for sku-like token
    for ln in lines:
        for tok in re.split(r'\s+', ln):
            if SKU_FIELD.match(tok):
                m = re.search(r'(\d+)', ln)
                return tok, (int(m.group(1)) if m else 1)
    return None, None


# def process_labels_single_pass(input_pdf: str,
#                                sku_mapping_csv: Optional[str],
#                                out_pdf: str,
#                                append_summary: bool = True) -> str:
#     """
#     Open input_pdf once, parse all pages using rawdict, extract sku/qty/bbox/text,
#     sort pages by parent sku and combo flag, and write final cropped LABEL_W x LABEL_H pages.
#     Optionally append summary pages into the same output.
#     """
#     if not os.path.exists(input_pdf):
#         raise FileNotFoundError(f"input pdf not found: {input_pdf}")

#     # load sku mapping if provided
#     child_to_parent = {}
#     if sku_mapping_csv and os.path.exists(sku_mapping_csv):
#         try:
#             df = pd.read_csv(sku_mapping_csv)
#             df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
#             if {'parent_sku', 'child_sku'}.issubset(df.columns):
#                 child_to_parent = dict(zip(df['child_sku'], df['parent_sku']))
#         except Exception as e:
#             print(f"⚠️ Warning: failed to load SKU mapping: {e}")

#     doc = fitz.open(input_pdf)
#     N = doc.page_count

#     pages_meta = []  # minimal metadata per page

#     for i in range(N):
#         page = doc[i]
#         raw = page.get_text("rawdict")    # single fast call per page
#         lines = _parse_lines_from_rawdict(raw)

#         sku, qty = _find_sku_qty_from_lines(lines)

#         # compute bbox from spans & image blocks in rawdict
#         bbox = None
#         for block in raw.get("blocks", []):
#             if block.get("type", 0) == 0:
#                 for line in block.get("lines", []):
#                     for span in line.get("spans", []):
#                         b = span.get("bbox")
#                         if b:
#                             r = fitz.Rect(b)
#                             bbox = r if bbox is None else bbox | r
#             elif block.get("type", 1):
#                 b = block.get("bbox")
#                 if b:
#                     r = fitz.Rect(b)
#                     bbox = r if bbox is None else bbox | r

#         if bbox is None or bbox.is_empty:
#             bbox = page.rect

#         # decide combo flag
#         txt_concat = " ".join(lines)
#         skus_all = SKU_FIELD.findall(txt_concat)
#         is_combo = False
#         if sku is None:
#             if skus_all:
#                 sku = skus_all[0]
#                 is_combo = len(skus_all) > 1
#             else:
#                 sku = f"unknown_{i:06d}"
#         else:
#             if len(skus_all) > 1 or (qty is not None and int(qty) > 1):
#                 is_combo = True

#         parent = child_to_parent.get(sku, sku)
#         pages_meta.append({
#             "index": i,
#             "parent": parent,
#             "sku": sku,
#             "qty": int(qty) if qty else 1,
#             "is_combo": is_combo,
#             "bbox": bbox,
#             "lines": lines,
#         })

#     # Sort: singles first (not combo), then by parent_sku, then sku
#     sorted_meta = sorted(pages_meta, key=lambda x: (not x["is_combo"], x["parent"].lower(), x["sku"].lower()))

#     # Build final document (create 100x100 pages in sorted order)
#     out_doc = fitz.open()
#     usable = fitz.Rect(OUTER_MARGIN, OUTER_MARGIN, LABEL_W - OUTER_MARGIN, LABEL_H - OUTER_MARGIN)
#     inner = fitz.Rect(usable.x0 + INNER_PADDING, usable.y0 + INNER_PADDING, usable.x1 - INNER_PADDING, usable.y1 - INNER_PADDING)

#     for m in sorted_meta:
#         idx = m["index"]
#         bbox = m["bbox"].intersect(doc[idx].rect)
#         if bbox.is_empty:
#             bbox = doc[idx].rect
#         content_w, content_h = bbox.width, bbox.height
#         if content_w <= 0 or content_h <= 0:
#             scale = 1.0
#         else:
#             scale = min(inner.width / content_w, inner.height / content_h, 1.0)
#         scaled_w = content_w * scale
#         scaled_h = content_h * scale
#         dx = inner.x0 + (inner.width - scaled_w) / 2
#         dy = inner.y0 + (inner.height - scaled_h) / 2
#         dest = fitz.Rect(dx, dy, dx + scaled_w, dy + scaled_h)

#         new_page = out_doc.new_page(width=LABEL_W, height=LABEL_H)
#         new_page.show_pdf_page(dest, doc, idx, clip=bbox)

#     # Optionally append summary pages (built from pages_meta)
#     if append_summary:
#         sku_groups = defaultdict(list)
#         courier_counts = defaultdict(int)
#         company_counts = defaultdict(int)

#         for m in pages_meta:
#             lines = m["lines"]
#             # extract table rows if possible
#             try:
#                 idx = next(j for j, ln in enumerate(lines) if ORDER_HEADER.search(ln))
#             except StopIteration:
#                 continue
#             if idx + 5 < len(lines):
#                 s = lines[idx + 1]
#                 size = lines[idx + 2] if idx + 2 < len(lines) else ""
#                 qty_raw = lines[idx + 3] if idx + 3 < len(lines) else "1"
#                 order_no = lines[idx + 5] if idx + 5 < len(lines) else ""
#                 mm = re.search(r"(\d+)", qty_raw)
#                 q = int(mm.group(1)) if mm else 1
#                 sku_groups[(s, size, q)].append(order_no)
#             # courier detection simple heuristic
#             for ln in lines:
#                 if "pickup" in ln.lower():
#                     courier_counts[ln.strip()] += 1
#                     break
#             for j, ln in enumerate(lines):
#                 if ln.strip() == "If undelivered, return to:":
#                     for k in range(j+1, len(lines)):
#                         if lines[k].strip():
#                             company_counts[lines[k].strip()] += 1
#                             break

#         if sku_groups:
#             lines_out = []
#             lines_out.append("LABEL SUMMARY")
#             lines_out.append("")
#             lines_out.append(f"Generated: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}")
#             lines_out.append("")
#             header = f"{'ORD':>5} {'QTY':>5} {'Size':<15} {'SKU'}"
#             lines_out.append(header)
#             lines_out.append("-" * len(header))
#             total_packages = 0
#             for (sku, size, qty), orders in sorted(sku_groups.items(), key=lambda x: (x[0][0].lower(), x[0][1].lower())):
#                 ord_count = len(orders)
#                 total_packages += ord_count
#                 lines_out.append(f"{ord_count:>5} {qty:>5} {size[:14]:<15} {sku}")
#             lines_out.append("")
#             lines_out.append(f"Total package: {total_packages}")
#             lines_out.append("")
#             lines_out.append("Courier wise total package:")
#             lines_out.append(f"{'Package':>7}  Courier Partner")
#             for courier, cnt in sorted(courier_counts.items(), key=lambda x: x[0].lower()):
#                 lines_out.append(f"{cnt:>7}  {courier}")
#             lines_out.append("")
#             lines_out.append("Company wise total package:")
#             lines_out.append(f"{'Package':>7}  Sold By")
#             for company, cnt in sorted(company_counts.items(), key=lambda x: x[0].lower()):
#                 lines_out.append(f"{cnt:>7}  {company}")

#             # chunk and write summary pages
#             font_size = 7
#             margin = 8
#             usable_height = LABEL_H - 2 * margin
#             line_h = font_size * 1.3
#             max_lines = max(5, int(usable_height // line_h))
#             for start in range(0, len(lines_out), max_lines):
#                 chunk = lines_out[start:start + max_lines]
#                 page = out_doc.new_page(width=LABEL_W, height=LABEL_H)
#                 rect = fitz.Rect(margin, margin, LABEL_W - margin, LABEL_H - margin)
#                 page.insert_textbox(rect, "\n".join(chunk), fontname="courier", fontsize=font_size, align=0)

#     # Save final output
#     os.makedirs(os.path.dirname(out_pdf) or ".", exist_ok=True)
#     out_doc.save(out_pdf)
#     out_doc.close()
#     doc.close()
#     print(f"✅ Final labels saved: {out_pdf} ({len(sorted_meta)} pages)")
#     return out_pdf


def process_labels_single_pass(input_pdf: str,
                               sku_mapping_csv: Optional[str],
                               out_pdf: str,
                               append_summary: bool = True) -> str:
    """
    Single-pass processor:
      - open input_pdf once
      - parse pages with rawdict, extract sku/qty/bbox/text
      - SKIP pages that do not contain any SKU token (selectable)
      - sort pages by parent sku and combo flag
      - write final cropped LABEL_W x LABEL_H pages
      - optionally append summary pages (built from kept pages)
    Returns out_pdf path.
    """
    if not os.path.exists(input_pdf):
        raise FileNotFoundError(f"input pdf not found: {input_pdf}")

    # load sku mapping if provided
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

    pages_meta = []  # minimal metadata per page (only pages WITH SKU)
    skipped_count = 0

    for i in range(N):
        page = doc[i]
        raw = page.get_text("rawdict")    # single fast call per page
        lines = _parse_lines_from_rawdict(raw)

        sku, qty = _find_sku_qty_from_lines(lines)

        # compute bbox from spans & image blocks in rawdict
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

        # gather all SKU-like tokens in page text (liberal scan)
        txt_concat = " ".join(lines)
        if not txt_concat.strip():
            # also try page.get_text("text") as a backup
            txt_concat = page.get_text("text") or ""

        skus_all = SKU_FIELD.findall(txt_concat)

        # DECISION: skip the page if there is no detectable SKU token
        if not skus_all and (sku is None):
            skipped_count += 1
            continue  # <-- skip page entirely

        # If SKU wasn't found via structured table parse, pick first found token
        if sku is None and skus_all:
            sku = skus_all[0]

        # qty fallback
        if qty is None:
            # try to find numeric qty nearby (fallback)
            m = re.search(r'(\d+)', txt_concat)
            qty = int(m.group(1)) if m else 1

        # decide combo flag
        is_combo = False
        if len(skus_all) > 1 or (qty is not None and int(qty) > 1):
            is_combo = True

        parent = child_to_parent.get(sku, sku)
        pages_meta.append({
            "index": i,
            "parent": parent,
            "sku": sku,
            "qty": int(qty) if qty else 1,
            "is_combo": is_combo,
            "bbox": bbox,
            "lines": lines,
        })

    # if no pages kept -> raise or return gracefully
    if not pages_meta:
        doc.close()
        raise RuntimeError("No label pages with SKU found in input PDF (all pages skipped).")

    # Sort: singles first (not combo), then by parent_sku, then sku
    sorted_meta = sorted(pages_meta, key=lambda x: (not x["is_combo"], x["parent"].lower(), x["sku"].lower()))

    # Build final document (create 100x100 pages in sorted order)
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

    # Optionally append summary pages (built from kept pages_meta)
    if append_summary:
        sku_groups = defaultdict(list)
        courier_counts = defaultdict(int)
        company_counts = defaultdict(int)

        for m in pages_meta:
            lines = m["lines"]
            # extract table rows if possible
            try:
                idx = next(j for j, ln in enumerate(lines) if ORDER_HEADER.search(ln))
            except StopIteration:
                continue
            if idx + 5 < len(lines):
                s = lines[idx + 1]
                size = lines[idx + 2] if idx + 2 < len(lines) else ""
                qty_raw = lines[idx + 3] if idx + 3 < len(lines) else "1"
                order_no = lines[idx + 5] if idx + 5 < len(lines) else ""
                mm = re.search(r"(\d+)", qty_raw)
                q = int(mm.group(1)) if mm else 1
                sku_groups[(s, size, q)].append(order_no)
            # courier detection simple heuristic
            for ln in lines:
                if "pickup" in ln.lower():
                    courier_counts[ln.strip()] += 1
                    break
            for j, ln in enumerate(lines):
                if ln.strip() == "If undelivered, return to:":
                    for k in range(j+1, len(lines)):
                        if lines[k].strip():
                            company_counts[lines[k].strip()] += 1
                            break

        if sku_groups:
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

            # chunk and write summary pages
            font_size = 7
            margin = 8
            usable_height = LABEL_H - 2 * margin
            line_h = font_size * 1.3
            max_lines = max(5, int(usable_height // line_h))
            for start in range(0, len(lines_out), max_lines):
                chunk = lines_out[start:start + max_lines]
                page = out_doc.new_page(width=LABEL_W, height=LABEL_H)
                rect = fitz.Rect(margin, margin, LABEL_W - margin, LABEL_H - margin)
                page.insert_textbox(rect, "\n".join(chunk), fontname="courier", fontsize=font_size, align=0)

    # Save final output
    os.makedirs(os.path.dirname(out_pdf) or ".", exist_ok=True)
    out_doc.save(out_pdf)
    out_doc.close()
    doc.close()

    print(f"✅ Final labels saved: {out_pdf} ({len(sorted_meta)} pages kept, {skipped_count} pages skipped)")
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
        # use rawdict for faster blocks detection
        raw = src_page.get_text("rawdict")
        for block in raw.get("blocks", []):
            if block.get("type", 0) == 0:
                r = None
                # first span bbox in line
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


def extract_items_from_label_lines(lines):
    """
    From a list of text 'lines' of a single label page, extract all
    (sku, size, qty, color, order_no) rows under the
    'SKU / Size / Qty / Color / Order No.' header.

    Works for single items AND combo orders (multiple rows).
    """
    items = []

    # Normalize whitespace and drop empty lines
    lines = [l.strip() for l in lines if l.strip()]

    # 1) locate header "Order No."
    try:
        idx = lines.index("Order No.")
    except ValueError:
        return items  # no product table on this page

    j = idx + 1

    # 2) walk in groups of 5 until we hit the next section
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


def normalize_courier(raw_name: str) -> str:
    """
    Normalize courier names using regex only.
    Handles variants like:
      - Valmo / ValmoPlus / Valmo Pickup 13/12
      - Xpress / Xpress Bees / Xpressbees
      - Delhivery / Delhivery Express
    """
    if not raw_name:
        return "Unknown"

    low = raw_name.lower()

    # Valmo family (Valmo, ValmoPlus, Valmo-XYZ)
    if re.search(r"\bvalmo", low):
        return "Valmo"

    # Xpressbees family
    if re.search(r"\bxpress", low):
        return "Xpressbees"

    # Delhivery family
    if re.search(r"\bdelhivery", low):
        return "Delhivery"

    # Ekart
    if re.search(r"\bekart", low):
        return "Ekart"

    # Shadowfax
    if re.search(r"\bshadowfax", low):
        return "Shadowfax"

    # Ecom Express
    if re.search(r"\becom\s*express", low):
        return "Ecom Express"

    # fallback – return cleaned original
    return raw_name.strip()


def extract_courier(lines):
    """
    Courier detection rules:
    1. Find ANY line containing the word 'pickup' (case-insensitive)
    2. If the SAME line contains 'valmo' (Valmo / ValmoPlus / etc) → return 'Valmo'
    3. Else: courier is the closest previous non-empty line
    4. Normalize known courier names
    """

    for i, ln in enumerate(lines):
        low = ln.lower()

        if re.search(r"\bpickup\b", low):
            # CASE A: Valmo mentioned in same line
            if re.search(r"\bvalmo", low):
                return "Valmo"

            # CASE B: courier is on previous line
            j = i - 1
            while j >= 0:
                prev = lines[j].strip()
                if prev:
                    return normalize_courier(prev)
                j -= 1

            # CASE C: fallback to same line
            return normalize_courier(ln.strip())

    return "Unknown"


# Optional: keep compatibility wrappers (if other code expects these names)
def sort_pdf_by_parent_sku(*args, **kwargs):
    raise NotImplementedError("sort_pdf_by_parent_sku is deprecated; use process_labels_single_pass instead.")

def crop_and_fit_labels(*args, **kwargs):
    raise NotImplementedError("crop_and_fit_labels is deprecated; use process_labels_single_pass instead.")

def append_summary_page(labels_pdf: str):
    """
    Robust summary appender: finds product rows using a permissive 'Order No' header search,
    extracts all SKU/Size/Qty rows per page (including combo rows), aggregates counts,
    and appends one-or-more summary pages to the same PDF.
    """
    if not os.path.exists(labels_pdf):
        print(f"⚠️ Summary: file not found: {labels_pdf}")
        return

    doc = fitz.open(labels_pdf)

    sku_groups = defaultdict(list)   # (sku, size, qty) -> [order_no, ...]
    courier_counts = defaultdict(int)
    company_counts = defaultdict(int)

    def _lines_from_page(page):
        """Return normalized text lines from a page using rawdict (more robust)."""
        raw = page.get_text("rawdict")
        lines = []
        for block in raw.get("blocks", []):
            if block.get("type", 0) != 0:  # skip image blocks for text lines
                continue
            for line in block.get("lines", []):
                spans = [sp.get("text", "").strip() for sp in line.get("spans", []) if sp.get("text", "").strip()]
                if spans:
                    lines.append(" ".join(spans))
        # fallback to text if rawdict yields nothing
        if not lines:
            txt = page.get_text("text") or ""
            lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        return lines

    header_re = re.compile(r'\bOrder\s*No\.?\b', re.IGNORECASE)

    total_item_rows = 0
    pages_with_items = 0

    for p_idx in range(doc.page_count):
        page = doc[p_idx]
        lines = _lines_from_page(page)
        if not lines:
            continue

        # Find a header line index using regex rather than exact match
        header_idx = None
        for j, ln in enumerate(lines):
            if header_re.search(ln):
                header_idx = j
                break

        if header_idx is None:
            continue

        # Extract item rows from the page lines using your helper.
        items = extract_items_from_label_lines(lines[header_idx:])  # pass only the tail starting at header
        if not items:
            continue

        pages_with_items += 1
        total_item_rows += len(items)

        for sku, size, qty, color, order in items:
            # normalize qty to int if possible
            try:
                q = int(re.search(r'\d+', qty).group(0)) if qty and re.search(r'\d+', qty) else 1
            except Exception:
                q = 1
            sku_groups[(sku, size, q)].append(order or "")

        # courier detection (best-effort) — same heuristic as before but using 'lines'
        courier = extract_courier(lines)
        courier_counts[courier] += 1

        # company detection (best-effort)
        company = "Unknown"
        for i, ln in enumerate(lines):
            if ln.strip().startswith("If undelivered, return to"):
                for k in range(i + 1, len(lines)):
                    if lines[k].strip():
                        company = lines[k].strip()
                        break
                break
        company_counts[company] += 1

    if not sku_groups:
        print("ℹ️ Summary: no label product rows found (no summary appended).")
        doc.close()
        return

    # Build summary text lines
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

    # Write summary pages into the document (use same page size as first page)
    first_rect = doc[0].rect if doc.page_count else fitz.Rect(0, 0, 283, 283)
    font_size = 7
    margin = 10
    usable_height = first_rect.height - 2 * margin
    line_height = font_size * 1.3
    max_lines = max(5, int(usable_height // line_height))

    for start in range(0, len(lines_out), max_lines):
        chunk = lines_out[start:start + max_lines]
        page = doc.new_page(width=first_rect.width, height=first_rect.height)
        rect = fitz.Rect(margin, margin, page.rect.width - margin, page.rect.height - margin)
        page.insert_textbox(rect, "\n".join(chunk), fontname="courier", fontsize=font_size, align=0)

    # Save changes incrementally (preserve original content)
    doc.save(labels_pdf, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()

    print(f"✅ Summary appended: pages with items={pages_with_items}, item rows={total_item_rows}, summary pages added={(len(lines_out) + max_lines - 1)//max_lines}")
