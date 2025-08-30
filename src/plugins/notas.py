from dataclasses import dataclass, field
from typing import Dict, Any, List
import logging

from utils import word_in_text

logger = logging.getLogger(__name__)


@dataclass
class Plugin:
    """Plugin para tomar notas mediante dictado."""
    name: str = "notas"
    awaiting: bool = field(default=False, init=False)

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        return self.awaiting or word_in_text(text, "nota", config)

    def run(self, text: str, ctx):  # ctx: PluginCtx
        if self.awaiting:
            note = text.strip()
            notas: List[str] = ctx.memory.get("notes", [])
            notas.append(note)
            ctx.memory.set("notes", notas)
            logger.info(f"[Plugin:notas] Guardada nota: {note}")
            ctx.speak("Nota guardada")
            self.awaiting = False
            return

        # Extraer nota en la misma frase si es posible
        partes = text.split(" ", 1)
        if len(partes) > 1 and word_in_text(partes[0], "nota", ctx.config):
            note = partes[1].strip()
            notas: List[str] = ctx.memory.get("notes", [])
            notas.append(note)
            ctx.memory.set("notes", notas)
            logger.info(f"[Plugin:notas] Guardada nota: {note}")
            ctx.speak("Nota guardada")
        else:
            self.awaiting = True
            ctx.speak("¿Qué nota quieres guardar?")
