import yaml
from pathlib import Path
from typing import Any, Dict, List
import threading

class MemoryStore:
    """Almacén simple de memoria persistente en YAML."""
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        if path.exists():
            with path.open('r', encoding='utf-8') as f:
                self.data: Dict[str, Any] = yaml.safe_load(f) or {}
        else:
            self.data = {}
        self.data.setdefault('history', [])

    def add_history(self, text: str) -> None:
        with self.lock:
            self.data.setdefault('history', []).append(text)
            self.save()

    def get_history(self) -> List[str]:
        with self.lock:
            return list(self.data.get('history', []))

    def set(self, key: str, value: Any) -> None:
        with self.lock:
            self.data[key] = value
            self.save()

    def get(self, key: str, default: Any = None) -> Any:
        with self.lock:
            return self.data.get(key, default)

    def save(self) -> None:
        with self.lock:
            with self.path.open('w', encoding='utf-8') as f:
                yaml.safe_dump(self.data, f)

