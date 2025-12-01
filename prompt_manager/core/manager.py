from core.models import Prompt
from core.storage import JSONStorage
from datetime import datetime


class PromptManager:
    def __init__(self, storage: JSONStorage):
        self.storage = storage
        self.data = self.storage.load()

    # ---------- Category Operations ----------

    def add_category(self, category_name: str):
        if category_name in self.data["categories"]:
            return f"Category '{category_name}' already exists."
        self.data["categories"][category_name] = []
        self.storage.save(self.data)
        return f"Category '{category_name}' added."

    def delete_category(self, category_name: str):
        if category_name not in self.data["categories"]:
            return f"Category '{category_name}' not found."
        del self.data["categories"][category_name]
        self.storage.save(self.data)
        return f"Category '{category_name}' deleted."
    
    def rename_category(self, old_name: str, new_name: str):
        if old_name not in self.data["categories"]:
            return f"Category '{old_name}' not found."
        if new_name in self.data["categories"]:
            return f"Category '{new_name}' already exists."

        # Move prompts to new category name
        self.data["categories"][new_name] = self.data["categories"].pop(old_name)
        self.storage.save(self.data)
        return f"Category '{old_name}' renamed to '{new_name}'."

    

    # ---------- Prompt Operations ----------

    def add_prompt(self, category: str, title: str, description: str):
        if category not in self.data["categories"]:
            return f"Category '{category}' does not exist."

        prompt = Prompt.create(title, description)
        self.data["categories"][category].append(prompt.to_dict())
        self.storage.save(self.data)
        return f"Prompt '{title}' added under '{category}'."

    def update_prompt(self, category: str, prompt_id: str, new_title: str, new_description: str):
        if category not in self.data["categories"]:
            return f"Category '{category}' not found."

        prompts = self.data["categories"][category]
        for p in prompts:
            if p["id"] == prompt_id:
                p["title"] = new_title
                p["description"] = new_description
                p["updated_at"] = datetime.now().isoformat()
                self.storage.save(self.data)
                return f"Prompt '{prompt_id}' updated."
        return f"Prompt '{prompt_id}' not found."

    def delete_prompt(self, category: str, prompt_id: str):
        if category not in self.data["categories"]:
            return f"Category '{category}' not found."

        before = len(self.data["categories"][category])
        self.data["categories"][category] = [
            p for p in self.data["categories"][category] if p["id"] != prompt_id
        ]
        after = len(self.data["categories"][category])

        if before == after:
            return f"Prompt '{prompt_id}' not found."
        self.storage.save(self.data)
        return f"Prompt '{prompt_id}' deleted."

    # ---------- Search ----------
    def search_prompts(self, keyword: str):
        results = []
        for category, prompts in self.data["categories"].items():
            for p in prompts:
                if keyword.lower() in p["title"].lower() or keyword.lower() in p["description"].lower():
                    results.append((category, p))
        return results

    # ---------- Utility ----------
    def list_categories(self):
        return list(self.data["categories"].keys())

    def list_prompts(self, category: str):
        return self.data["categories"].get(category, [])
