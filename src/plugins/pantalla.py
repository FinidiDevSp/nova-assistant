from dataclasses import dataclass
from typing import Dict, Any
import re
import platform
import subprocess
import logging

from utils import word_in_text

try:
    import screen_brightness_control as sbc
except Exception:  # library not available
    sbc = None

logger = logging.getLogger(__name__)


@dataclass
class Plugin:
    name: str = "pantalla"

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        t = text.lower()
        if word_in_text(text, "brillo", config):
            return True
        if word_in_text(text, "apaga", config) and word_in_text(text, "pantalla", config):
            return True
        if word_in_text(text, "enciende", config) and word_in_text(text, "pantalla", config):
            return True
        return False

    def run(self, text: str, ctx):  # ctx: PluginCtx
        t = text.lower()
        if word_in_text(text, "apaga", ctx.config) and word_in_text(text, "pantalla", ctx.config):
            sysname = platform.system()
            try:
                if sysname == "Windows":
                    import ctypes
                    ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
                elif sysname == "Linux":
                    subprocess.run(["xset", "dpms", "force", "off"], check=False)
                else:
                    ctx.speak("No sé apagar la pantalla en este sistema")
                    return
                ctx.speak("Pantalla apagada")
            except Exception as e:
                logger.error(f"[Plugin:pantalla] Error apagando pantalla: {e}")
                ctx.speak("No pude apagar la pantalla")
            return

        if word_in_text(text, "enciende", ctx.config) and word_in_text(text, "pantalla", ctx.config):
            sysname = platform.system()
            try:
                if sysname == "Windows":
                    import ctypes
                    ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, -1)
                elif sysname == "Linux":
                    subprocess.run(["xset", "dpms", "force", "on"], check=False)
                else:
                    ctx.speak("No sé encender la pantalla en este sistema")
                    return
                ctx.speak("Pantalla encendida")
            except Exception as e:
                logger.error(f"[Plugin:pantalla] Error encendiendo pantalla: {e}")
                ctx.speak("No pude encender la pantalla")
            return

        if word_in_text(text, "brillo", ctx.config):
            if sbc is None:
                ctx.speak("No puedo controlar el brillo en este sistema")
                return
            m = re.search(r"(\d+)", t)
            if not m:
                ctx.speak("No entendí el nivel de brillo")
                return
            level = int(m.group(1))
            level = max(0, min(100, level))
            try:
                sbc.set_brightness(level)
                ctx.speak(f"Brillo ajustado al {level} por ciento")
            except Exception as e:
                logger.error(f"[Plugin:pantalla] Error: {e}")
                ctx.speak("No pude ajustar el brillo")
