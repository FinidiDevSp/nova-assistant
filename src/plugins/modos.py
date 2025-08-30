"""Plugin para gestionar modos configurables mediante YAML."""

from dataclasses import dataclass
from typing import Dict, Any
import subprocess
import yaml

@dataclass
class Plugin:
    name: str = "modos"
    _modos: Dict[str, Any] | None = None

    def _load_config(self, ctx):
        if self._modos is not None:
            return
        cfg_path = ctx.config_dir / 'modos.yaml'
        if cfg_path.exists():
            with cfg_path.open('r', encoding='utf-8') as f:
                self._modos = yaml.safe_load(f) or {}
        else:
            self._modos = {}

    def match(self, text: str, config: Dict[str, Any]) -> bool:
        return "modo" in text.lower()

    def run(self, text: str, ctx):  # ctx: PluginCtx
        self._load_config(ctx)
        t = text.lower()
        parts = t.split("modo", 1)
        if len(parts) < 2:
            return
        mode = parts[1].strip()
        cfg = self._modos.get(mode)
        if not cfg:
            ctx.speak(f"Modo {mode} no encontrado")
            return
        ctx.memory.set('last_mode', mode)
        speak_text = cfg.get('speak')
        if speak_text:
            ctx.speak(speak_text)
        for cmd in cfg.get('commands', []):
            try:
                subprocess.Popen(cmd, shell=True)
            except Exception as e:
                print(f"[Plugin:modos] Error ejecutando {cmd}: {e}")
        ctx.speak(f"Modo {mode} activado")

