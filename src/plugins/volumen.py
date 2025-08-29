"""Plugin para ajustar el volumen del sistema en Windows.

Reacciona a frases como "volumen 50" o "sube el volumen al 20" y
establece el volumen maestro al porcentaje indicado (0-100).
"""

from dataclasses import dataclass
from typing import Dict, Any
import re
import platform


@dataclass
class Plugin:
    name: str = "volumen"

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        """Comprueba si el texto contiene la palabra "volumen" y un número."""
        return "volumen" in text.lower() and re.search(r"\d+", text) is not None

    def run(self, text: str, ctx):  # ctx: PluginCtx
        m = re.search(r"(\d+)", text)
        if not m:
            ctx.speak("No entendí el nivel de volumen")
            return
        level = int(m.group(1))
        level = max(0, min(100, level))

        if platform.system() != "Windows":
            ctx.speak("El control de volumen solo funciona en Windows")
            return

        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            ctx.speak(f"Volumen ajustado al {level} por ciento")
        except Exception as e:
            print(f"[Plugin:volumen] Error: {e}")
            ctx.speak("No pude ajustar el volumen")
