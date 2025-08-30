from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo

from utils import word_in_text


@dataclass
class Plugin:
    """Plugin que responde con la hora actual."""
    name: str = "hora"

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        # Coincide si se pregunta por la hora.
        return word_in_text(text, "hora", config)

    def run(self, text: str, ctx):
        tz = ZoneInfo("Europe/Madrid")
        ahora = datetime.now(tz)
        ctx.speak(f"Son las {ahora.hour:02d}:{ahora.minute:02d}")
