from dataclasses import dataclass
from typing import Dict, Any
import webbrowser
import logging

from utils import word_in_text

logger = logging.getLogger(__name__)


@dataclass
class Plugin:
    name: str = "navegador"

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        t = text.lower()
        if word_in_text(text, "navegador", config):
            return True
        # permitir mencionar navegadores específicos
        if any(b in t for b in ("chrome", "firefox", "edge")):
            return True
        return False

    def run(self, text: str, ctx):  # ctx: PluginCtx
        t = text.lower()
        browser = ctx.config.get("browser", "")
        url = ctx.config.get("browser_url", "https://www.google.com")
        try:
            # prioriza navegador mencionado en el texto
            if "chrome" in t:
                browser = "chrome"
            elif "firefox" in t:
                browser = "firefox"
            elif "edge" in t:
                browser = "edge"
            if browser:
                try:
                    webbrowser.get(browser).open(url, new=1)
                except webbrowser.Error:
                    logger.warning(f"Navegador '{browser}' no encontrado. Usando el predeterminado")
                    webbrowser.open(url, new=1)
            else:
                webbrowser.open(url, new=1)
            ctx.speak("Abriendo el navegador")
        except Exception as e:
            logger.error(f"[Plugin:navegador] Error: {e}")
            ctx.speak("No pude abrir el navegador")
