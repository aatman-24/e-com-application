import pandas as pd
from pathlib import Path
import subprocess
from pathlib import Path

def ensure_xlsx(file_path: str) -> str:
    """
    If input file is .xls, convert to .xlsx and return new path.
    If already .xlsx, return as-is.
    """
    path = Path(file_path)

    if path.suffix.lower() == ".xlsx":
        return str(path)

    if path.suffix.lower() != ".xls":
        raise ValueError("Unsupported file format. Please select .xls or .xlsx")

    # Convert .xls → .xlsx
    new_path = path.with_suffix(".xlsx")

    # Read all sheets
    xls = pd.ExcelFile(path)
    with pd.ExcelWriter(new_path, engine="openpyxl") as writer:
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    return str(new_path)


def ensure_xlsx_with_libreoffice(file_path: str) -> str:
    """
    Convert .xls to .xlsx ONCE.
    If .xlsx already exists, reuse it.
    """
    path = Path(file_path)

    # If already xlsx → use directly
    if path.suffix.lower() == ".xlsx":
        return str(path)

    if path.suffix.lower() != ".xls":
        raise ValueError("Unsupported file format")

    xlsx_path = path.with_suffix(".xlsx")

    # IMPORTANT: reuse existing converted file
    if xlsx_path.exists():
        return str(xlsx_path)

    # Convert only once
    cmd = [
        "libreoffice",
        "--headless",
        "--convert-to",
        "xlsx",
        str(path),
        "--outdir",
        str(path.parent)
    ]

    subprocess.run(cmd, check=True)

    if not xlsx_path.exists():
        raise RuntimeError("LibreOffice conversion failed")

    return str(xlsx_path)
