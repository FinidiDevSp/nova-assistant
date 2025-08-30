from dataclasses import dataclass
from typing import Dict, Any
import os
import platform
import logging

from utils import word_in_text

logger = logging.getLogger(__name__)


@dataclass
class Plugin:
    name: str = "sistema"

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        t = text.lower()
        if word_in_text(text, "hiberna", config) or word_in_text(text, "suspende", config):
            return True
        if word_in_text(text, "apaga", config) and any(word in t for word in ("ordenador", "equipo", "sistema", "pc", "computadora")):
            return True
        return False

    def run(self, text: str, ctx):  # ctx: PluginCtx
        t = text.lower()
        sysname = platform.system()
        try:
            if word_in_text(text, "hiberna", ctx.config) or word_in_text(text, "suspende", ctx.config):
                if sysname == "Windows":
                    os.system("shutdown /h")
                elif sysname == "Linux":
                    os.system("systemctl hibernate")
                else:
                    ctx.speak("No sé hibernar este sistema")
                    return
                ctx.speak("Hibernando el ordenador")
            elif word_in_text(text, "apaga", ctx.config):
                if sysname == "Windows":
                    os.system("shutdown /s /t 0")
                elif sysname == "Linux":
                    os.system("systemctl poweroff")
                else:
                    ctx.speak("No sé apagar este sistema")
                    return
                ctx.speak("Apagando el ordenador")
        except Exception as e:
            logger.error(f"[Plugin:sistema] Error: {e}")
            ctx.speak("No pude completar la acción solicitada")
