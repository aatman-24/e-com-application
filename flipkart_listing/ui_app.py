# # app.py

# import sys, json
# from PyQt5.QtWidgets import (
#     QApplication, QWidget, QLabel, QLineEdit,
#     QPushButton, QVBoxLayout, QHBoxLayout,
#     QMessageBox, QScrollArea, QFileDialog
# )
# from logic import generate_rows
# from excel_writer import write_rows_to_excel

# SHEET_NAME = "kids_apparel_combo"

# with open("config/defaults.json") as f:
#     DEFAULTS = json.load(f)


# class CatalogApp(QWidget):
#     def __init__(self):
#         super().__init__()
#         self.setWindowTitle("Flipkart Catalog Generator")
#         self.setGeometry(200, 100, 850, 750)

#         self.inputs = {}
#         self.excel_path = ""

#         self.init_ui()

#     def init_ui(self):
#         main_layout = QVBoxLayout()

#         # ---------- FILE PICKER ----------
#         file_row = QHBoxLayout()
#         self.file_input = QLineEdit()
#         self.file_input.setPlaceholderText("Select kids_apparel_combo.xlsx file")
#         browse_btn = QPushButton("Browse")
#         browse_btn.clicked.connect(self.browse_file)

#         file_row.addWidget(QLabel("Input Excel File"))
#         file_row.addWidget(self.file_input)
#         file_row.addWidget(browse_btn)
#         main_layout.addLayout(file_row)

#         # ---------- SCROLLABLE FORM ----------
#         scroll = QScrollArea()
#         container = QWidget()
#         form_layout = QVBoxLayout(container)

#         def add_field(label, value=""):
#             row = QHBoxLayout()
#             lbl = QLabel(label)
#             lbl.setFixedWidth(300)
#             edit = QLineEdit()
#             edit.setText(str(value))
#             row.addWidget(lbl)
#             row.addWidget(edit)
#             form_layout.addLayout(row)
#             self.inputs[label] = edit

#         # Required inputs
#         add_field("Base SKU")
#         add_field(
#             "Prices (comma separated)",
#             "420,430,430,440,440,450,450,460,460,470,470,480,480,490"
#         )

#         # Dynamic fields from defaults.json
#         for key, value in DEFAULTS.items():
#             add_field(key, value)

#         scroll.setWidget(container)
#         scroll.setWidgetResizable(True)
#         main_layout.addWidget(scroll)

#         # ---------- ACTION BUTTON ----------
#         generate_btn = QPushButton("Generate Catalog")
#         generate_btn.clicked.connect(self.generate)
#         main_layout.addWidget(generate_btn)

#         self.setLayout(main_layout)

#     def browse_file(self):
#         file_path, _ = QFileDialog.getOpenFileName(
#             self,
#             "Select Flipkart Excel File",
#             "",
#             "Excel Files (*.xlsx)"
#         )
#         if file_path:
#             self.excel_path = file_path
#             self.file_input.setText(file_path)

#     def generate(self):
#         try:
#             if not self.excel_path:
#                 raise ValueError("Please select the Excel input file")

#             base_sku = self.inputs["Base SKU"].text().strip()
#             if not base_sku:
#                 raise ValueError("Base SKU is required")

#             prices = [
#                 int(p.strip())
#                 for p in self.inputs["Prices (comma separated)"].text().split(",")
#             ]

#             base_data = {
#                 k: v.text()
#                 for k, v in self.inputs.items()
#                 if k not in ["Base SKU", "Prices (comma separated)"]
#             }

#             rows = generate_rows(base_sku, base_data, prices)

#             write_rows_to_excel(
#                 excel_path=self.excel_path,
#                 sheet_name=SHEET_NAME,
#                 rows=rows
#             )

#             QMessageBox.information(
#                 self,
#                 "Success",
#                 "14 size-wise rows generated successfully"
#             )

#         except Exception as e:
#             QMessageBox.critical(self, "Error", str(e))


# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = CatalogApp()
#     window.show()
#     sys.exit(app.exec_())


# app.py

import sys, json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QMessageBox, QScrollArea,
    QFileDialog, QGroupBox, QComboBox
)
from logic import generate_rows
from excel_writer import write_rows_to_excel
from excel_converter import ensure_xlsx_with_libreoffice



SHEET_NAME = "kids_apparel_combo"

# ---------- LOAD DEFAULTS ----------
with open("config/defaults.json") as f:
    DEFAULTS = json.load(f)

with open("config/prices.json") as f:
    DEFAULT_PRICES = json.load(f)["prices"]

with open("config/dropdowns.json") as f:
    DROPDOWNS = json.load(f)

# ---------- FIELD GROUPING (UI ONLY) ----------
MAIN_FIELDS = [
    "Base SKU",
    "Prices (comma separated)"
]

CLOTHING_FIELDS = [
    "Ideal For",
    "Primary Product Type",
    "Secondary Product Type",
    "Brand Color",
    "Primary Color",
    "Secondary Color",
    "Sleeve Length",
    "Pattern/Print Type"
]

PRODUCT_FIELDS = [
    "Main Image URL",
    "Other Image URL 1",
    "Other Image URL 2",
    "Other Image URL 3",
    "Description",
    "Search Keywords",
    "Key Features"
]

NON_TOUCHABLE_FIELDS = [
    "Listing Status", "MRP (INR)", "Fullfilment by", "Procurement type",
    "Procurement SLA (DAY)", "Stock", "Shipping provider",
    "Local handling fee (INR)", "Zonal handling fee (INR)",
    "National handling fee (INR)", "Length (CM)", "Breadth (CM)",
    "Height (CM)", "Weight (KG)", "HSN", "Luxury Cess",
    "Country Of Origin", "Manufacturer Details", "Packer Details",
    "Importer Details", "Tax Code", "Minimum Order Quantity (MinOQ)",
    "Brand", "Fabric", "Pattern", "Occasion", "Suitable For",
    "Fabric Care", "Style Code", "Items Included",
    "Other Dimensions", "Other Features", "Fabric Details", "Detail Placement", "Character"
]

class CatalogApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flipkart Catalog Generator")
        self.setGeometry(120, 60, 950, 820)

        self.inputs = {}
        self.excel_path = ""

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # ---------- FILE PICKER ----------
        file_row = QHBoxLayout()
        self.file_input = QLineEdit()
        browse_btn = QPushButton("Browse Excel")
        browse_btn.clicked.connect(self.browse_file)

        file_row.addWidget(QLabel("Input Excel File"))
        file_row.addWidget(self.file_input)
        file_row.addWidget(browse_btn)
        main_layout.addLayout(file_row)

        # ---------- SCROLLABLE FORM ----------
        scroll = QScrollArea()
        container = QWidget()
        form_layout = QVBoxLayout(container)

        def add_group(title, fields):
            group = QGroupBox(title)
            layout = QVBoxLayout()

            for field in fields:
                row = QHBoxLayout()
                label = QLabel(field)
                label.setFixedWidth(320)

                default_value = str(DEFAULTS.get(field, ""))

                if field in DROPDOWNS:
                    widget = QComboBox()
                    widget.addItems(DROPDOWNS[field])
                    if default_value in DROPDOWNS[field]:
                        widget.setCurrentText(default_value)
                else:
                    widget = QLineEdit()
                    widget.setText(default_value)

                row.addWidget(label)
                row.addWidget(widget)
                layout.addLayout(row)

                self.inputs[field] = widget

            group.setLayout(layout)
            form_layout.addWidget(group)

        # ---------- MAIN SECTION ----------
        main_group = QGroupBox("Main Section")
        main_layout_inner = QVBoxLayout()

        # Base SKU
        row1 = QHBoxLayout()
        lbl1 = QLabel("Base SKU")
        lbl1.setFixedWidth(320)
        self.inputs["Base SKU"] = QLineEdit()
        row1.addWidget(lbl1)
        row1.addWidget(self.inputs["Base SKU"])
        main_layout_inner.addLayout(row1)

        # Prices (auto-loaded)
        row2 = QHBoxLayout()
        lbl2 = QLabel("Prices (comma separated)")
        lbl2.setFixedWidth(320)
        self.inputs["Prices (comma separated)"] = QLineEdit(
            ",".join(str(p) for p in DEFAULT_PRICES)
        )
        row2.addWidget(lbl2)
        row2.addWidget(self.inputs["Prices (comma separated)"])
        main_layout_inner.addLayout(row2)

        main_group.setLayout(main_layout_inner)
        form_layout.addWidget(main_group)

        # ---------- OTHER SECTIONS ----------
        add_group("Clothing Details", CLOTHING_FIELDS)
        add_group("Product Details", PRODUCT_FIELDS)
        add_group("Other Details", NON_TOUCHABLE_FIELDS)

        scroll.setWidget(container)
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)

        # ---------- GENERATE BUTTON ----------
        btn = QPushButton("Generate Catalog")
        btn.clicked.connect(self.generate)
        main_layout.addWidget(btn)

        self.setLayout(main_layout)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Excel File", "", "Excel Files (*.xls *.xlsx)"
        )
        if path:
            self.excel_path = path
            self.file_input.setText(path)

    def generate(self):
        try:
            # ---------- BASIC VALIDATION ----------
            if not self.excel_path:
                raise ValueError("Please select the Excel input file")

            base_sku = self.inputs["Base SKU"].text().strip()
            if not base_sku:
                raise ValueError("Base SKU is required")

            # ---------- PRICES ----------
            prices_text = self.inputs["Prices (comma separated)"].text().strip()
            prices = [int(p.strip()) for p in prices_text.split(",") if p.strip()]

            if len(prices) != 14:
                raise ValueError("Exactly 14 prices are required (one per size)")

            # ---------- COLLECT ALL OTHER FIELDS ----------
            base_data = {}

            for field, widget in self.inputs.items():
                if field in ["Base SKU", "Prices (comma separated)"]:
                    continue

                # QComboBox (dropdown)
                if hasattr(widget, "currentText"):
                    base_data[field] = widget.currentText()

                # QLineEdit (text input)
                else:
                    base_data[field] = widget.text()

            # ---------- GENERATE ROWS ----------
            rows = generate_rows(
                base_sku=base_sku,
                base_data=base_data,
                prices=prices
            )

            # Convert using LibreOffice (SAFE)
            xlsx_path = ensure_xlsx_with_libreoffice(self.excel_path)

            # ---------- WRITE TO EXCEL ----------
            write_rows_to_excel(
                excel_path=xlsx_path,
                sheet_name=SHEET_NAME,
                rows=rows
            )

            QMessageBox.information(
                self,
                "Success",
                "14 size-wise rows generated successfully"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CatalogApp()
    window.show()
    sys.exit(app.exec_())
