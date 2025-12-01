import json
import os


class JSONStorage:
    
    def __init__(self, file_path="data/prompts.json"):
        self.file_path = file_path
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                json.dump({"categories": {}}, f, indent=4)

    def load(self):
        with open(self.file_path, "r") as f:
            return json.load(f)

    def save(self, data):
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=4)
