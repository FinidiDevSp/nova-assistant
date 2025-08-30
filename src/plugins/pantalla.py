from dataclasses import dataclass
from typing import Dict, Any
import re
import platform
import subprocess

try:
    import screen_brightness_control as sbc
except Exception:  # library not available
    sbc = None


@dataclass
class Plugin:
    name: str = "pantalla"

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        t = text.lower()
        if "brillo" in t:
            return True
        if "apaga" in t and "pantalla" in t:
            return True
        return False

    def run(self, text: str, ctx):  # ctx: PluginCtx
        t = text.lower()
        if "apaga" in t and "pantalla" in t:
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
                print(f"[Plugin:pantalla] Error apagando pantalla: {e}")
                ctx.speak("No pude apagar la pantalla")
            return

        if "brillo" in t:
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
                print(f"[Plugin:pantalla] Error: {e}")
                ctx.speak("No pude ajustar el brillo")
