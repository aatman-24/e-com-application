#!/usr/bin/env python3
"""
meesho_gui.py

PyQt5 GUI wrapper for:
 - generate N bordered images from an input image
 - for each generated image: upload -> fetchDuplicatePid -> getTransferPrice
 - write results_<timestamp>.csv into output_dir with columns: file_name, shipping_charges
"""

import sys
import os
import time
import csv
import tempfile
import random
import colorsys
import json
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

import requests
from PIL import Image, ImageOps

from PyQt5 import QtCore, QtGui, QtWidgets


# ---------------------------
# Default API endpoints/config
# ---------------------------

IMAGE_UPLOAD_URL = "https://supplier.meesho.com/catalogingapi/api/singleCatalogUpload/uploadSingleCatalogImages"
FETCH_DUP_PID_URL = "https://supplier.meesho.com/catalogingapi/api/priceRecommendation/fetchDuplicatePid"
FEE_URL = "https://supplier.meesho.com/catalogingapi/api/singleCatalogUpload/getTransferPrice"

# REFERER is now built dynamically as:
# https://supplier.meesho.com/panel/v3/new/cataloging/{identifier}/catalogs/single/add
REFERER_TEMPLATE = "https://supplier.meesho.com/panel/v3/new/cataloging/{identifier}/catalogs/single/add"

# Base headers (identifier + referer will be injected at runtime)
COMMON_HEADERS_TEMPLATE = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-GB,en;q=0.9",
    "browser-id": "NnAgKyAyMnQgKyAxejQxNDAxejQxNDBv",
    "client-package-version": "1.0.1",
    "client-type": "d-web",
    "origin": "https://supplier.meesho.com",
    "priority": "u=1, i",
    "sec-ch-ua": '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "sec-gpc": "1",
    # identifier, referer, and supplier-id will be added later
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
}

# ---------------------------
# Network / processing helpers
# ---------------------------

def parse_cookie_string(cookie_str: str) -> dict:
    d = {}
    for part in cookie_str.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            d[k.strip()] = v.strip()
    return d

def ensure_image_allowed_and_prepare(path: Path) -> Tuple[str, str, str, bool]:
    """Return (file_path, mime, send_name, temp_flag). Convert to PNG if needed."""
    if not path.exists():
        raise FileNotFoundError(path)
    fmt = None
    try:
        with Image.open(path) as im:
            fmt = im.format
    except Exception:
        fmt = None
    allowed = {"PNG", "JPEG", "JPG"}
    if fmt and fmt.upper() in allowed:
        mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
        return str(path), mime, path.name, False
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp_name = tmp.name
    tmp.close()
    with Image.open(path) as im:
        im.convert("RGBA").save(tmp_name, format="PNG")
    return tmp_name, "image/png", Path(tmp_name).name, True

def upload_image(session: requests.Session, image_path: Path, headers_base: dict) -> Dict[str, Any]:
    file_path, mime, send_name, is_temp = ensure_image_allowed_and_prepare(image_path)
    files = {"file": (send_name, open(file_path, "rb"), mime)}
    data = {"data": "undefined"}
    headers = dict(headers_base)

    

    try:
        resp = session.post(IMAGE_UPLOAD_URL, headers=headers, files=files, data=data, timeout=30)
    finally:
        try:
            files["file"][1].close()
        except Exception:
            pass
    if is_temp:
        try:
            os.unlink(file_path)
        except Exception:
            pass
    out = {"status_code": resp.status_code, "ok": resp.ok}
    try:
        out["json"] = resp.json()
    except Exception:
        out["json"] = None
        out["text"] = resp.text[:2000]
    return out

def poll_cdn_for_url(session: requests.Session, url: str, headers_base: dict, tries:int=8, delay:float=1.0) -> Tuple[bool, Dict[str,Any]]:
    last_status = None
    for _ in range(tries):
        try:
            r = session.get(url, headers={**headers_base, "accept":"*/*"}, timeout=10)
            last_status = getattr(r, "status_code", None)
            if r.status_code == 200:
                return True, {"status_code":200, "content_length": r.headers.get("content-length")}
        except Exception as e:
            last_status = str(e)
        time.sleep(delay)
    return False, {"last_status": last_status}

def call_fetch_duplicate_pid(session: requests.Session, image_url: str, headers_base: dict, base_payload: dict) -> Dict[str,Any]:
    headers = {**headers_base, "content-type": "application/json;charset=UTF-8"}
    payload = dict(base_payload)
    payload["image_url"] = image_url
    print("payload: ", payload)
    print("session: ", session)
    try:
        r = session.post(FETCH_DUP_PID_URL, headers=headers, json=payload, timeout=30)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    out = {"ok": r.ok, "status_code": r.status_code}
    try:
        out["json"] = r.json()
    except Exception:
        out["json"] = None
        out["text"] = r.text[:2000]
    return out

def extract_duplicate_pid(fetch_resp_json: Dict[str,Any]) -> Optional[int]:
    if not isinstance(fetch_resp_json, dict):
        return None
    d = fetch_resp_json.get("data") or {}
    if isinstance(d, dict) and "duplicate_pid" in d:
        try:
            return int(d["duplicate_pid"])
        except Exception:
            return None
    # fallback deep search
    def deep_search(obj):
        if isinstance(obj, dict):
            if "duplicate_pid" in obj:
                return obj["duplicate_pid"]
            for v in obj.values():
                found = deep_search(v)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for it in obj:
                found = deep_search(it)
                if found is not None:
                    return found
        return None
    found = deep_search(fetch_resp_json)
    try:
        return int(found) if found is not None else None
    except Exception:
        return None

def call_get_transfer_price(session: requests.Session, payload: Dict[str,Any], headers_base: dict) -> Dict[str,Any]:
    headers = {**headers_base, "content-type": "application/json;charset=UTF-8"}
    try:
        r = session.post(FEE_URL, headers=headers, json=payload, timeout=30)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    out = {"ok": r.ok, "status_code": r.status_code}
    try:
        out["json"] = r.json()
    except Exception:
        out["json"] = None
        out["text"] = r.text[:2000]
    return out

def contains_fee(json_obj) -> bool:
    if not isinstance(json_obj, dict):
        return False
    for k in ("shipping_charges", "transfer_price", "total_price", "shipping_fee", "price"):
        if k in json_obj:
            return True
    return False

# ---------------------------
# Image generation (borders)
# ---------------------------

def generate_hsl_colors(count):
    colors = []
    for i in range(count):
        h = i / float(count)
        r, g, b = colorsys.hsv_to_rgb(h, 0.9, 0.9)
        colors.append((int(r*255), int(g*255), int(b*255)))
    return colors

def generate_random_colors(count):
    return [(random.randint(20,235), random.randint(20,235), random.randint(20,235)) for _ in range(count)]

def add_border(img: Image.Image, thickness: int, color):
    return ImageOps.expand(img, border=thickness, fill=color)

# ---------------------------
# Worker thread class
# ---------------------------

class WorkerSignals(QtCore.QObject):
    progress = QtCore.pyqtSignal(int)            # int percent
    log = QtCore.pyqtSignal(str)                 # log line
    finished = QtCore.pyqtSignal(str)            # csv path when finished
    aborted = QtCore.pyqtSignal()

class Worker(QtCore.QRunnable):
    """
    Worker that runs the generate + upload + fetchDuplicatePid + getTransferPrice pipeline.
    Emits progress/log signals.
    """
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.signals = WorkerSignals()
        self._is_abort = False

    def abort(self):
        self._is_abort = True

    def run(self):
        try:
            csv_path = self._run_pipeline()
            if self._is_abort:
                self.signals.aborted.emit()
            else:
                self.signals.finished.emit(csv_path)
        except Exception as e:
            self.signals.log.emit(f"ERROR: {e}")
            self.signals.finished.emit("")  # finished but empty

    def _run_pipeline(self) -> str:
        conf = self.config
        out_dir = Path(conf["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)

        # generate images
        src = Image.open(conf["input_image"]).convert("RGB")
        colors = generate_hsl_colors(conf["num_images"]) if conf["color_mode"] == "hsl" else generate_random_colors(conf["num_images"])
        generated = []
        self.signals.log.emit(f"Generating {len(colors)} images into {out_dir} ...")
        for idx, color in enumerate(colors, 1):
            if self._is_abort:
                self.signals.log.emit("Aborting during generation.")
                return ""
            bordered = add_border(src, conf["border_thickness"], color)
            timestamp = int(time.time() * 1000)
            fname = f"{idx}_{timestamp}.png"
            p = out_dir / fname
            bordered.save(p)
            generated.append(p)
            self.signals.log.emit(f"Generated: {p.name}")

        # prepare session
        session = requests.Session()
        session.cookies.update(parse_cookie_string(conf["cookie_string"]))

        headers = dict(COMMON_HEADERS_TEMPLATE)
        identifier = conf["identifier"]
        referer_page = conf["referer_page"]

        headers["identifier"] = identifier
        headers["referer"] = referer_page



        # Try to get supplier-id automatically from cookie (safer)
        cookie_supplier = (
            session.cookies.get("supplier_id")
            or session.cookies.get("supplier-id")
        )
        if cookie_supplier:
            headers["supplier-id"] = str(cookie_supplier)
        else:
            # fallback to the value from UI if cookie doesn't have it
            headers["supplier-id"] = str(conf["supplier_id"])

        session.headers.update(headers)


        # supplier-id from cookie if available (more reliable)
        cookie_supplier = None
        for key in ["supplier_id", "supplier-id", "supplierId"]:
            val = session.cookies.get(key)
            if val:
                cookie_supplier = val
                break

        if cookie_supplier:
            headers["supplier-id"] = str(cookie_supplier)
            self.signals.log.emit(f"Using supplier-id from cookie: {cookie_supplier}")
        else:
            self.signals.log.emit("WARNING: No supplier id found in COOKIE_STRING; upload may fail.")

        session.headers.clear()
        session.headers.update(headers)

        # open csv for this run
        run_ts = int(time.time() * 1000)
        csv_file = out_dir / f"results_{run_ts}.csv"
        self.signals.log.emit(f"Writing results to {csv_file}")

        with open(csv_file, "w", newline="", encoding="utf-8") as csvf:
            writer = csv.DictWriter(csvf, fieldnames=["file_name","shipping_charges"])
            writer.writeheader()

            total = len(generated)
            for i, p in enumerate(generated, 1):
                if self._is_abort:
                    self.signals.log.emit("Aborting before processing next image.")
                    break
                self.signals.log.emit(f"\n--- Processing {p.name} ({i}/{total}) ---")

                # Step 1: upload
                up = upload_image(session, p, headers)
                self.signals.log.emit(f"Upload HTTP: {up.get('status_code')}")
                if up.get("json"):
                    self.signals.log.emit(f"Upload JSON: {json.dumps(up['json'], ensure_ascii=False)}")
                else:
                    self.signals.log.emit(f"Upload text: {up.get('text')}")
                if not up.get("ok") or not up.get("json"):
                    self.signals.log.emit(f"❌ Upload failed for {p.name} — skipping.")
                    writer.writerow({"file_name": p.name, "shipping_charges": ""})
                    percent = int((i/total)*100)
                    self.signals.progress.emit(percent)
                    continue

                # get image_url
                image_url = None
                if isinstance(up.get("json"), dict):
                    for k in ("image","fileUrl","imageUrl","url"):
                        if k in up["json"]:
                            image_url = up["json"][k]; break
                if not image_url:
                    self.signals.log.emit("❌ Upload returned no image_url — skipping.")
                    writer.writerow({"file_name": p.name, "shipping_charges": ""})
                    percent = int((i/total)*100)
                    self.signals.progress.emit(percent)
                    continue

                # small wait + refresh referer + poll CDN
                time.sleep(1.2)
                try:
                    session.get(referer_page, timeout=10)
                except Exception:
                    pass
                ok, info = poll_cdn_for_url(session, image_url, headers, tries=conf["cdn_tries"], delay=conf["cdn_delay"])
                self.signals.log.emit(f"CDN reachable: {ok} {info}")

                # Step 2: fetch duplicate pid (retry)
                duplicate_pid = None
                for attempt in range(1, conf["fetch_dup_retries"]+1):
                    if self._is_abort:
                        break
                    fr = call_fetch_duplicate_pid(session, image_url, headers, conf["fetch_dup_base"])
                    self.signals.log.emit(f"fetchDuplicatePid status: {fr.get('status_code')}")
                    if fr.get("json"):
                        self.signals.log.emit(f"fetchDuplicatePid JSON: {json.dumps(fr['json'], ensure_ascii=False)}")
                        duplicate_pid = extract_duplicate_pid(fr["json"])
                        if duplicate_pid:
                            self.signals.log.emit(f"Found duplicate_pid: {duplicate_pid}")
                            break
                        else:
                            self.signals.log.emit("No duplicate_pid in response yet (data empty).")
                    else:
                        self.signals.log.emit(f"fetchDuplicatePid text: {fr.get('text')}")
                    time.sleep(conf["fetch_dup_delay"])

                if not duplicate_pid:
                    self.signals.log.emit(f"❌ Could not obtain duplicate_pid for {p.name} — skipping fee. ")
                    writer.writerow({"file_name": p.name, "shipping_charges": ""})
                    percent = int((i/total)*100)
                    self.signals.progress.emit(percent)
                    continue

                # Step 3: getTransferPrice (retry)
                fee_payload = dict(conf["fee_base"])
                fee_payload["duplicate_pid"] = duplicate_pid
                fee_resp = None
                for attempt in range(1, conf["fee_retries"]+1):
                    if self._is_abort:
                        break
                    fr = call_get_transfer_price(session, fee_payload, headers)
                    self.signals.log.emit(f"getTransferPrice status: {fr.get('status_code')}")
                    if fr.get("json"):
                        self.signals.log.emit(f"getTransferPrice JSON: {json.dumps(fr['json'], ensure_ascii=False)}")
                        if contains_fee(fr["json"]) and fr.get("status_code") == 200:
                            fee_resp = fr
                            break
                    else:
                        self.signals.log.emit(f"getTransferPrice text: {fr.get('text')}")
                    time.sleep(conf["fee_delay"])

                if not fee_resp:
                    self.signals.log.emit(f"❌ Could not fetch fee for {p.name} — writing blank shipping.")
                    writer.writerow({"file_name": p.name, "shipping_charges": ""})
                    percent = int((i/total)*100)
                    self.signals.progress.emit(percent)
                    continue

                # write shipping value
                fee_json = fee_resp["json"]
                shipping = fee_json.get("shipping_charges") or fee_json.get("shipping_fee") or fee_json.get("shipping") or ""
                writer.writerow({"file_name": p.name, "shipping_charges": shipping})
                self.signals.log.emit(f"Saved row: {p.name}, shipping_charges={shipping}")

                percent = int((i/total)*100)
                self.signals.progress.emit(percent)

        return str(csv_file)

# ---------------------------
# PyQt5 UI
# ---------------------------

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Meesho Bulk Border + Shipping Checker")
        self.setMinimumSize(800, 600)

        w = QtWidgets.QWidget()
        self.setCentralWidget(w)
        layout = QtWidgets.QVBoxLayout(w)

        # form grid
        form = QtWidgets.QGridLayout()
        layout.addLayout(form)

        # Input image picker
        form.addWidget(QtWidgets.QLabel("Source image:"), 0, 0)
        self.le_image = QtWidgets.QLineEdit()
        form.addWidget(self.le_image, 0, 1)
        btn_browse = QtWidgets.QPushButton("Browse...")
        form.addWidget(btn_browse, 0, 2)
        btn_browse.clicked.connect(self.browse_image)

        # COOKIE + SSCAT + Supplier + Identifier row
        cookie_label = QtWidgets.QLabel("COOKIE_STRING (paste entire cookie header):")
        layout.addWidget(cookie_label)

        cookie_row = QtWidgets.QHBoxLayout()
        layout.addLayout(cookie_row)

        # left: cookie box (shorter)
        self.te_cookie = QtWidgets.QPlainTextEdit()
        self.te_cookie.setPlaceholderText("cookie1=val; cookie2=val; ...")
        self.te_cookie.setMaximumHeight(60)
        cookie_row.addWidget(self.te_cookie, 3)

        # right: SSCAT ID, Supplier ID, Identifier
        id_form = QtWidgets.QFormLayout()

        self.le_sscat_id = QtWidgets.QLineEdit()
        self.le_sscat_id.setValidator(QtGui.QIntValidator(1, 10**9, self))
        self.le_sscat_id.setText("10285")   # default

        self.le_supplier_id = QtWidgets.QLineEdit()
        self.le_supplier_id.setValidator(QtGui.QIntValidator(1, 10**9, self))
        self.le_supplier_id.setText("2989863")  # default (you can change)

        self.le_identifier = QtWidgets.QLineEdit()
        self.le_identifier.setPlaceholderText("e.g. bwqsg or zmkwe")
        self.le_identifier.setText("zmkwe")  # default based on your current example

        id_form.addRow("SSCAT ID:", self.le_sscat_id)
        id_form.addRow("Supplier ID:", self.le_supplier_id)
        id_form.addRow("Identifier:", self.le_identifier)

        cookie_row.addLayout(id_form, 1)

        # Border thickness + num images + output dir
        form2 = QtWidgets.QHBoxLayout()
        layout.addLayout(form2)
        form2.addWidget(QtWidgets.QLabel("Border thickness (px):"))
        self.sb_thickness = QtWidgets.QSpinBox()
        self.sb_thickness.setRange(1, 200)
        self.sb_thickness.setValue(4)
        form2.addWidget(self.sb_thickness)

        form2.addSpacing(12)
        form2.addWidget(QtWidgets.QLabel("Num images:"))
        self.sb_num = QtWidgets.QSpinBox()
        self.sb_num.setRange(1, 200)
        self.sb_num.setValue(30)
        form2.addWidget(self.sb_num)

        form2.addSpacing(12)
        form2.addWidget(QtWidgets.QLabel("Output dir:"))

        downloads_dir = os.path.expanduser("~/Downloads")
        default_out = str(Path(downloads_dir, "generated_border").resolve())
        self.le_outdir = QtWidgets.QLineEdit(default_out)
        Path(default_out).parent.mkdir(parents=True, exist_ok=True)
        form2.addWidget(self.le_outdir)
        btn_out = QtWidgets.QPushButton("Select")
        form2.addWidget(btn_out)
        btn_out.clicked.connect(self.browse_outdir)

        # start/stop buttons
        buttons = QtWidgets.QHBoxLayout()
        layout.addLayout(buttons)
        self.btn_start = QtWidgets.QPushButton("Start")
        self.btn_stop = QtWidgets.QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        buttons.addWidget(self.btn_start)
        buttons.addWidget(self.btn_stop)

        # progress & log
        self.progress = QtWidgets.QProgressBar()
        layout.addWidget(self.progress)
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        # open folder button
        btn_open = QtWidgets.QPushButton("Open output folder")
        layout.addWidget(btn_open)

        # signals
        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)
        btn_open.clicked.connect(self.open_output_folder)

        self.pool = QtCore.QThreadPool.globalInstance()
        self.worker_obj = None

    def browse_image(self):
        start_dir = os.path.expanduser("~/Downloads")
        f, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select source image",
            start_dir,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if f:
            self.le_image.setText(f)

    def browse_outdir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Select output directory", ".")
        if d:
            self.le_outdir.setText(str(Path(d).resolve()))

    def append_log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {text}")
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def start(self):
        input_image = self.le_image.text().strip()
        cookie = self.te_cookie.toPlainText().strip()
        sscat_id_text = self.le_sscat_id.text().strip()
        supplier_id_text = self.le_supplier_id.text().strip()
        identifier_text = self.le_identifier.text().strip()

        if not input_image or not Path(input_image).exists():
            QtWidgets.QMessageBox.warning(self, "Missing input image", "Please select a valid source image file.")
            return
        if not cookie:
            QtWidgets.QMessageBox.warning(self, "Missing COOKIE_STRING", "Please paste your COOKIE_STRING.")
            return
        if not sscat_id_text or not supplier_id_text or not identifier_text:
            QtWidgets.QMessageBox.warning(self, "Missing fields", "Please enter SSCAT ID, Supplier ID, and Identifier.")
            return

        try:
            sscat_id = int(sscat_id_text)
            supplier_id = int(supplier_id_text)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid IDs", "SSCAT ID and Supplier ID must be numbers.")
            return

        outdir = Path(self.le_outdir.text()).expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        referer_page = REFERER_TEMPLATE.format(identifier=identifier_text)

        config = {
            "input_image": input_image,
            "border_thickness": int(self.sb_thickness.value()),
            "num_images": int(self.sb_num.value()),
            "color_mode": "hsl",
            "output_dir": str(outdir),
            "cookie_string": cookie,
            "sscat_id": sscat_id,
            "supplier_id": supplier_id,
            "identifier": identifier_text,
            "referer_page": referer_page,
            "cdn_tries": 8,
            "cdn_delay": 1.0,
            "fetch_dup_retries": 2,
            "fetch_dup_delay": 1.5,
            "fee_retries": 6,
            "fee_delay": 1.0,
            "fetch_dup_base": {
                "is_old_image_match_enabled": True,
                "sscat_id": sscat_id,
            },
            "fee_base": {
                "sscat_id": sscat_id,
                "gst_percentage": 5,
                "price": 100,
                "supplier_id": supplier_id,
                "gst_type": "GSTIN",
            },
        }

        self.progress.setValue(0)
        self.log.clear()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

        worker = Worker(config)
        worker.signals.progress.connect(self.progress.setValue)
        worker.signals.log.connect(self.append_log)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.aborted.connect(self._on_aborted)

        self.worker_obj = worker
        self.pool.start(worker)
        self.append_log("Processing...")

    def stop(self):
        if self.worker_obj:
            self.worker_obj.abort()
            self.append_log("Stopping... please wait")
            self.btn_stop.setEnabled(False)

    def _on_finished(self, csv_path: str):
        if csv_path:
            self.append_log(f"Finished. CSV: {csv_path}")
        else:
            self.append_log("Finished (no CSV produced).")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress.setValue(100)

    def _on_aborted(self):
        self.append_log("Worker aborted by user.")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def open_output_folder(self):
        d = Path(self.le_outdir.text()).expanduser().resolve()
        if not d.exists():
            QtWidgets.QMessageBox.information(self, "No output", f"Output folder does not exist: {d}")
            return
        if sys.platform.startswith("linux"):
            os.system(f'xdg-open "{d}"')
        elif sys.platform == "darwin":
            os.system(f'open "{d}"')
        elif sys.platform == "win32":
            os.startfile(str(d))

# ---------------------------
# entrypoint
# ---------------------------

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
