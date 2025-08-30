from dataclasses import dataclass
from typing import Dict, Any, List
import threading
import re
import logging

from utils import word_in_text

logger = logging.getLogger(__name__)


@dataclass
class Plugin:
    """Plugin para programar alarmas/temporizadores."""
    name: str = "alarma"

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        t = text.lower()
        return word_in_text(text, "alarma", config) or word_in_text(text, "temporizador", config)

    def run(self, text: str, ctx):  # ctx: PluginCtx
        t = text.lower()
        m = re.search(r"(\d+)\s*(segundo|segundos|minuto|minutos|hora|horas)", t)
        if not m:
            ctx.speak("No entendí el tiempo de la alarma")
            return
        cantidad = int(m.group(1))
        unidad = m.group(2)
        segundos = cantidad
        if unidad.startswith("minuto"):
            segundos *= 60
        elif unidad.startswith("hora"):
            segundos *= 3600

        logger.info(f"[Plugin:alarma] Programando alarma en {segundos} segundos")
        ctx.speak(f"Alarma en {cantidad} {unidad}")

        def avisar():
            ctx.speak("¡Alarma!")

        timer = threading.Timer(segundos, avisar)
        timer.daemon = True
        timer.start()

        alarms: List[Dict[str, Any]] = ctx.memory.get("alarms", [])
        alarms.append({"original": text, "seconds": segundos})
        ctx.memory.set("alarms", alarms)
