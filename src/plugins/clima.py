from dataclasses import dataclass
from typing import Dict, Any
import urllib.request
import urllib.parse
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class Plugin:
    name: str = "clima"

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        t = text.lower()
        return "clima" in t or "tiempo" in t

    def run(self, text: str, ctx):  # ctx: PluginCtx
        city = ctx.config.get("weather_city") or ctx.config.get("city")
        if not city:
            ctx.speak("No hay una ciudad configurada para el clima")
            return
        try:
            url_city = urllib.parse.quote(city)
            url = f"https://wttr.in/{url_city}?format=j1"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.load(response)
            current = data["current_condition"][0]
            temp = current.get("temp_C")
            desc = current.get("weatherDesc", [{}])[0].get("value", "")
            frase = f"El clima en {city} es {desc} con {temp} grados Celsius"
            logger.info(f"[Plugin:clima] -> {frase}")
            ctx.speak(frase)
        except Exception as e:
            logger.error(f"[Plugin:clima] Error: {e}")
            ctx.speak("No pude obtener el clima")
