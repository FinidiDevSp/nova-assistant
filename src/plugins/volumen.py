"""Plugin para ajustar el volumen del sistema en Windows.

Reacciona a frases como "volumen 50", "sube el volumen" o "silencia el volumen"
y ajusta el volumen maestro según corresponda.
"""

from dataclasses import dataclass
from typing import Dict, Any
import re
import platform
import logging

logger = logging.getLogger(__name__)


@dataclass
class Plugin:
    name: str = "volumen"

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        """Comprueba si el texto contiene la palabra 'volumen' y alguna acción."""
        t = text.lower()
        if "volumen" not in t:
            return False
        if re.search(r"\d+", t):
            return True
        return any(k in t for k in ["sube", "baja", "silencia", "activa"])

    def run(self, text: str, ctx):  # ctx: PluginCtx
        if platform.system() != "Windows":
            ctx.speak("El control de volumen solo funciona en Windows")
            return

        t = text.lower()

        try:
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))

            if "sube" in t:
                current = volume.GetMasterVolumeLevelScalar()
                level = min(1.0, current + 0.05)
                volume.SetMasterVolumeLevelScalar(level, None)
                ctx.speak("Volumen aumentado")
                return

            if "baja" in t:
                current = volume.GetMasterVolumeLevelScalar()
                level = max(0.0, current - 0.05)
                volume.SetMasterVolumeLevelScalar(level, None)
                ctx.speak("Volumen disminuido")
                return

            if "silencia" in t:
                volume.SetMute(1, None)
                ctx.speak("Volumen silenciado")
                return

            if "activa" in t:
                volume.SetMute(0, None)
                ctx.speak("Volumen activado")
                return

            m = re.search(r"(\d+)", t)
            if not m:
                ctx.speak("No entendí el nivel de volumen")
                return
            level = int(m.group(1))
            level = max(0, min(100, level))
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            ctx.speak(f"Volumen ajustado al {level} por ciento")
        except Exception as e:
            logger.error(f"[Plugin:volumen] Error: {e}")
            ctx.speak("No pude ajustar el volumen")
