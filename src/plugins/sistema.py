from dataclasses import dataclass
from typing import Dict, Any
import os
import platform


@dataclass
class Plugin:
    name: str = "sistema"

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        t = text.lower()
        if "hibern" in t or "susp" in t:
            return True
        if "apaga" in t and any(word in t for word in ("ordenador", "equipo", "sistema", "pc", "computadora")):
            return True
        return False

    def run(self, text: str, ctx):  # ctx: PluginCtx
        t = text.lower()
        sysname = platform.system()
        try:
            if "hibern" in t or "susp" in t:
                if sysname == "Windows":
                    os.system("shutdown /h")
                elif sysname == "Linux":
                    os.system("systemctl hibernate")
                else:
                    ctx.speak("No sé hibernar este sistema")
                    return
                ctx.speak("Hibernando el ordenador")
            elif "apaga" in t:
                if sysname == "Windows":
                    os.system("shutdown /s /t 0")
                elif sysname == "Linux":
                    os.system("systemctl poweroff")
                else:
                    ctx.speak("No sé apagar este sistema")
                    return
                ctx.speak("Apagando el ordenador")
        except Exception as e:
            print(f"[Plugin:sistema] Error: {e}")
            ctx.speak("No pude completar la acción solicitada")
