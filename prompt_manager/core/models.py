from dataclasses import dataclass, asdict
from datetime import datetime
import uuid


@dataclass
class Prompt:
    id: str
    title: str
    description: str
    created_at: str
    updated_at: str

    @staticmethod
    def create(title: str, description: str):
        now = datetime.now().isoformat()
        return Prompt(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            created_at=now,
            updated_at=now
        )

    def to_dict(self):
        return asdict(self)
