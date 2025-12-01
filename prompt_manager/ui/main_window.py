import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QTextEdit, QLineEdit, QLabel,
    QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt

from core.storage import JSONStorage
from core.manager import PromptManager


class PromptManagerUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Prompt Manager")
        self.setGeometry(100, 100, 1000, 600)

        # Backend manager
        self.manager = PromptManager(JSONStorage())

        # --- Main layout setup ---
        container = QWidget()
        main_layout = QHBoxLayout()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # ---------- Left Sidebar (Categories) ----------
        self.category_list = QListWidget()
        self.category_list.itemClicked.connect(self.load_prompts)
        self.refresh_categories()

        cat_button_layout = QVBoxLayout()
        
        # self.add_cat_btn = QPushButton("+ Add Category")
        # self.del_cat_btn = QPushButton("− Delete Category")
        # self.add_cat_btn.clicked.connect(self.add_category)
        # self.del_cat_btn.clicked.connect(self.delete_category)
        # cat_button_layout.addWidget(self.add_cat_btn)
        # cat_button_layout.addWidget(self.del_cat_btn)
        self.add_cat_btn = QPushButton("+ Add Category")
        self.rename_cat_btn = QPushButton("✏️ Rename Category")
        self.del_cat_btn = QPushButton("− Delete Category")

        self.add_cat_btn.clicked.connect(self.add_category)
        self.rename_cat_btn.clicked.connect(self.rename_category)
        self.del_cat_btn.clicked.connect(self.delete_category)

        cat_button_layout.addWidget(self.add_cat_btn)
        cat_button_layout.addWidget(self.rename_cat_btn)
        cat_button_layout.addWidget(self.del_cat_btn)

        cat_button_layout.addStretch()

        sidebar_layout = QVBoxLayout()
        sidebar_layout.addWidget(QLabel("Categories"))
        sidebar_layout.addWidget(self.category_list)
        sidebar_layout.addLayout(cat_button_layout)

        sidebar_widget = QWidget()
        sidebar_widget.setLayout(sidebar_layout)
        sidebar_widget.setFixedWidth(250)

        # ---------- Right Side (Prompts) ----------
        right_layout = QVBoxLayout()

        # Search bar
        search_layout = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search prompts...")
        self.search_bar.textChanged.connect(self.search_prompts)
        search_layout.addWidget(QLabel("🔍"))
        search_layout.addWidget(self.search_bar)

        # Prompt list
        self.prompt_list = QListWidget()
        self.prompt_list.itemClicked.connect(self.display_prompt)

        # Buttons
        prompt_btn_layout = QHBoxLayout()
        self.add_prompt_btn = QPushButton("+ Add Prompt")
        self.edit_prompt_btn = QPushButton("✏️ Edit")
        self.del_prompt_btn = QPushButton("🗑 Delete")
        self.add_prompt_btn.clicked.connect(self.add_prompt)
        self.edit_prompt_btn.clicked.connect(self.edit_prompt)
        self.del_prompt_btn.clicked.connect(self.delete_prompt)
        prompt_btn_layout.addWidget(self.add_prompt_btn)
        prompt_btn_layout.addWidget(self.edit_prompt_btn)
        prompt_btn_layout.addWidget(self.del_prompt_btn)

        # Description editor
        self.prompt_detail = QTextEdit()
        self.prompt_detail.setReadOnly(True)

        right_layout.addLayout(search_layout)
        right_layout.addWidget(QLabel("Prompts"))
        right_layout.addWidget(self.prompt_list)
        right_layout.addLayout(prompt_btn_layout)
        right_layout.addWidget(QLabel("Description"))
        right_layout.addWidget(self.prompt_detail)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        # Add both to main layout
        main_layout.addWidget(sidebar_widget)
        main_layout.addWidget(right_widget)

    # ---------- Category Management ----------
    def refresh_categories(self):
        self.category_list.clear()
        for c in self.manager.list_categories():
            self.category_list.addItem(c)

    def add_category(self):
        name, ok = QInputDialog.getText(self, "Add Category", "Category Name:")
        if ok and name:
            msg = self.manager.add_category(name)
            QMessageBox.information(self, "Info", msg)
            self.refresh_categories()

    def delete_category(self):
        item = self.category_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a category to delete.")
            return
        name = item.text()
        msg = self.manager.delete_category(name)
        QMessageBox.information(self, "Info", msg)
        self.refresh_categories()
        self.prompt_list.clear()
        self.prompt_detail.clear()


    def rename_category(self):
        item = self.category_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a category to rename.")
            return

        old_name = item.text()

        # Ask for the new category name (pre-filled with old name)
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Category",
            "Enter new category name:",
            text=old_name
        )

        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()

        # Backend rename
        msg = self.manager.rename_category(old_name, new_name)
        QMessageBox.information(self, "Info", msg)

        self.refresh_categories()

        # If renamed category is currently selected, reload its prompts
        if new_name in self.manager.list_categories():
            items = self.category_list.findItems(new_name, Qt.MatchExactly)
            if items:
                self.category_list.setCurrentItem(items[0])
                self.load_prompts()


    # ---------- Prompt Management ----------
    def load_prompts(self):
        category = self.category_list.currentItem().text()
        self.prompt_list.clear()
        for p in self.manager.list_prompts(category):
            self.prompt_list.addItem(f"{p['title']} | {p['id']}")

    def add_prompt(self):
        item = self.category_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Warning", "Select a category first.")
            return
        category = item.text()
        title, ok = QInputDialog.getText(self, "Add Prompt", "Prompt Title:")
        if not ok or not title:
            return
        desc, ok = QInputDialog.getMultiLineText(self, "Prompt Description", "Enter Description:")
        if not ok:
            return
        msg = self.manager.add_prompt(category, title, desc)
        QMessageBox.information(self, "Info", msg)
        self.load_prompts()

    # def edit_prompt(self):
    #     category_item = self.category_list.currentItem()
    #     prompt_item = self.prompt_list.currentItem()
    #     if not category_item or not prompt_item:
    #         QMessageBox.warning(self, "Warning", "Select a prompt to edit.")
    #         return

    #     category = category_item.text()
    #     prompt_id = prompt_item.text().split("|")[-1].strip()
    #     new_title, ok = QInputDialog.getText(self, "Edit Prompt", "New Title:")
    #     if not ok or not new_title:
    #         return
    #     new_desc, ok = QInputDialog.getMultiLineText(self, "Edit Description", "New Description:")
    #     if not ok:
    #         return

    #     msg = self.manager.update_prompt(category, prompt_id, new_title, new_desc)
    #     QMessageBox.information(self, "Info", msg)
    #     self.load_prompts()

    def edit_prompt(self):
        category_item = self.category_list.currentItem()
        prompt_item = self.prompt_list.currentItem()

        if not category_item or not prompt_item:
            QMessageBox.warning(self, "Warning", "Select a prompt to edit.")
            return

        category = category_item.text()
        prompt_id = prompt_item.text().split("|")[-1].strip()

        # Find the current prompt
        current_prompt = None
        for p in self.manager.list_prompts(category):
            if p["id"] == prompt_id:
                current_prompt = p
                break

        if not current_prompt:
            QMessageBox.warning(self, "Error", "Prompt not found.")
            return

        # Pre-fill existing title and description
        old_title = current_prompt["title"]
        old_desc = current_prompt["description"]

        # Ask for updated title
        new_title, ok = QInputDialog.getText(
            self,
            "Edit Prompt Title",
            "Prompt Title:",
            text=old_title  # pre-fill old title
        )
        if not ok or not new_title.strip():
            return

        # Ask for updated description
        new_desc, ok = QInputDialog.getMultiLineText(
            self,
            "Edit Prompt Description",
            "Prompt Description:",
            text=old_desc  # pre-fill old description
        )
        if not ok:
            return

        # Update prompt via manager
        msg = self.manager.update_prompt(category, prompt_id, new_title.strip(), new_desc.strip())
        QMessageBox.information(self, "Info", msg)

        # Refresh UI
        self.load_prompts()
        self.prompt_detail.setPlainText(new_desc)


    def delete_prompt(self):
        category_item = self.category_list.currentItem()
        prompt_item = self.prompt_list.currentItem()
        if not category_item or not prompt_item:
            QMessageBox.warning(self, "Warning", "Select a prompt to delete.")
            return
        category = category_item.text()
        prompt_id = prompt_item.text().split("|")[-1].strip()
        msg = self.manager.delete_prompt(category, prompt_id)
        QMessageBox.information(self, "Info", msg)
        self.load_prompts()
        self.prompt_detail.clear()

    def display_prompt(self):
        category = self.category_list.currentItem().text()
        prompt_id = self.prompt_list.currentItem().text().split("|")[-1].strip()
        for p in self.manager.list_prompts(category):
            if p["id"] == prompt_id:
                self.prompt_detail.setPlainText(p["description"])
                return

    def search_prompts(self):
        keyword = self.search_bar.text().strip()
        self.prompt_list.clear()
        if not keyword:
            if self.category_list.currentItem():
                self.load_prompts()
            return
        results = self.manager.search_prompts(keyword)
        for category, p in results:
            self.prompt_list.addItem(f"[{category}] {p['title']} | {p['id']}")
