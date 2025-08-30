# Plugin de saludo: reacciona a la palabra clave "saludame" en el texto
# y saluda por altavoz usando el nombre del config y la franja horaria.

from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from utils import word_in_text

logger = logging.getLogger(__name__)

@dataclass
class Plugin:
    name: str = "saludo"

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        # Soporta sinónimos definidos en config/synonyms.yaml
        return word_in_text(text, "saludame", config)

    def run(self, text: str, ctx):  # ctx: PluginCtx (tiene config y speak)
        nombre = ctx.config.get('person_name', 'amigo')
        tz = ZoneInfo("Europe/Madrid")
        h = datetime.now(tz).hour
        if 6 <= h < 12:
            saludo = "Buenos días"
        elif 12 <= h < 20:
            saludo = "Buenas tardes"
        else:
            saludo = "Buenas noches"
        frase = f"{saludo}, {nombre}."
        logger.info(f"[Plugin:saludo] -> {frase}")
        ctx.speak(frase)
