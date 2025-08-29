import os
import sys
import time
import json
import math
import queue
import importlib
import pathlib
from dataclasses import dataclass
from typing import Callable, List, Dict, Any

import yaml
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import pyttsx3
from datetime import datetime
from zoneinfo import ZoneInfo

# -------------------- Utilidades --------------------

def rms_energy_int16(block: bytes) -> float:
    """Calcula energía RMS aproximada de un bloque int16 mono."""
    if not block:
        return 0.0
    import array
    a = array.array('h')
    a.frombytes(block)
    if len(a) == 0:
        return 0.0
    accum = 0
    for s in a:
        accum += s * s
    mean_sq = accum / len(a)
    return math.sqrt(mean_sq)


def now_greeting_timeday_eu_madrid() -> str:
    tz = ZoneInfo("Europe/Madrid")
    hour = datetime.now(tz).hour
    if 6 <= hour < 12:
        return "Buenos días"
    elif 12 <= hour < 20:
        return "Buenas tardes"
    else:
        return "Buenas noches"


# -------------------- TTS (pyttsx3) --------------------

class Speaker:
    def __init__(self, language_hint: str = "es"):
        self.engine = pyttsx3.init()
        # Intenta seleccionar voz española si existe
        try:
            for v in self.engine.getProperty('voices'):
                name = (v.name or "").lower()
                lang = "".join(getattr(v, 'languages', []) or []).lower()
                if language_hint in name or language_hint in lang:
                    self.engine.setProperty('voice', v.id)
                    break
        except Exception:
            pass

    def say(self, text: str):
        self.engine.say(text)
        self.engine.runAndWait()


# -------------------- Plugins --------------------

@dataclass
class PluginCtx:
    config: Dict[str, Any]
    speak: Callable[[str], None]


def load_plugins(plugin_names: List[str]) -> List[Any]:
    plugins = []
    for name in plugin_names:
        module_name = f"plugins.{name}"
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, 'Plugin'):
                plugins.append(module.Plugin())
                print(f"[Plugins] Cargado: {name}")
            else:
                print(f"[Plugins] Aviso: {name} no expone clase Plugin")
        except Exception as e:
            print(f"[Plugins] Error cargando {name}: {e}")
    return plugins


def run_plugins(plugins: List[Any], text: str, ctx: PluginCtx):
    """Ejecuta plugins cuyo matcher devuelva True para el texto dado."""
    for p in plugins:
        try:
            if p.match(text, ctx.config):
                p.run(text, ctx)
        except Exception as e:
            print(f"[Plugins] Error en {getattr(p,'name','<plugin>')}: {e}")


# -------------------- Reconocimiento --------------------

class VoskListener:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.sample_rate = int(cfg.get('sample_rate', 16000))
        model_path = cfg['model_path']
        if not pathlib.Path(model_path).exists():
            print(f"Modelo no encontrado en {model_path}")
            sys.exit(1)
        print("Cargando modelo Vosk…")
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
        self.recognizer.SetWords(True)

        self.q: "queue.Queue[bytes]" = queue.Queue()
        self.activation = cfg.get('activation_word', 'activar').lower()
        self.stop_word = cfg.get('stop_word', 'parar').lower()
        self.silence_timeout = float(cfg.get('silence_timeout_sec', 1.2))
        self.energy_thresh = float(cfg.get('silence_energy_threshold', 650))

        self.mode = cfg.get('mode', 'keyword_once')  # 'keyword_once' | 'keyword_until_stop'
        self.active = False
        self.last_voice_ts = 0.0
        self.utterance_buffer: List[str] = []

    # Callback de audio
    def _cb(self, indata, frames, time_info, status):
        if status:
            print(status)
        self.q.put(bytes(indata))

    def _open_stream(self):
        return sd.RawInputStream(samplerate=self.sample_rate,
                                 blocksize=8000,
                                 dtype='int16',
                                 channels=1,
                                 callback=self._cb)

    def _handle_final_result(self, res_json: str) -> str:
        text = (json.loads(res_json).get('text') or '').strip()
        return text

    def _maybe_end_utterance(self, energy: float, now_ts: float) -> bool:
        """Devuelve True si llevamos silencio suficiente para cortar."""
        if energy < self.energy_thresh:
            if self.last_voice_ts == 0:
                self.last_voice_ts = now_ts
        else:
            self.last_voice_ts = 0
            return False

        if self.last_voice_ts > 0 and (now_ts - self.last_voice_ts) >= self.silence_timeout:
            self.last_voice_ts = 0
            return True
        return False

    def loop(self, plugins, speaker: Speaker):
        print("Escuchando… (Ctrl+C para salir)")
        ctx = PluginCtx(config=self.cfg, speak=speaker.say)
        with self._open_stream():
            while True:
                data: bytes = self.q.get()

                energy = rms_energy_int16(data)
                now_ts = time.time()

                if self.recognizer.AcceptWaveform(data):
                    text = self._handle_final_result(self.recognizer.Result()).lower()

                    if not self.active:
                        if self.activation in text:
                            self.active = True
                            self.utterance_buffer.clear()
                            print(f"[Hotword] Activación detectada: '{self.activation}'")
                            if self.mode == 'keyword_until_stop':
                                print("[Modo] Transcripción continua hasta 'stop_word'")
                        continue

                    if self.mode == 'keyword_until_stop':
                        if self.stop_word in text:
                            print(f"[Hotword] Parada detectada: '{self.stop_word}'")
                            self.active = False
                            self.utterance_buffer.clear()
                            continue

                        if text:
                            print(f"[ASR] {text}")
                            run_plugins(plugins, text, ctx)
                    else:
                        if text:
                            self.utterance_buffer.append(text)
                            self.last_voice_ts = 0

                        if self._maybe_end_utterance(energy, now_ts):
                            if self.utterance_buffer:
                                utterance = " ".join(self.utterance_buffer)
                                print(f"[ASR-ONCE] {utterance}")
                                run_plugins(plugins, utterance, ctx)
                            else:
                                print("[ASR-ONCE] (silencio, nada que transcribir)")
                            self.utterance_buffer.clear()
                            self.active = False

                else:
                    partial = (json.loads(self.recognizer.PartialResult()).get('partial') or '').lower()

                    if not self.active and partial:
                        if self.activation in partial:
                            self.active = True
                            self.utterance_buffer.clear()
                            print(f"[Hotword] Activación detectada (parcial): '{self.activation}'")
                            if self.mode == 'keyword_until_stop':
                                print("[Modo] Transcripción continua hasta 'stop_word'")
                        continue

                    if self.active and self.mode == 'keyword_until_stop' and partial:
                        if self.stop_word in partial:
                            print(f"[Hotword] Parada detectada (parcial): '{self.stop_word}'")
                            self.active = False
                            self.utterance_buffer.clear()
                            continue

                    if self.active and self.mode == 'keyword_once':
                        if self._maybe_end_utterance(energy, now_ts):
                            if self.utterance_buffer:
                                utterance = " ".join(self.utterance_buffer)
                                print(f"[ASR-ONCE] {utterance}")
                                run_plugins(plugins, utterance, ctx)
                            else:
                                print("[ASR-ONCE] (silencio, nada que transcribir)")
                            self.utterance_buffer.clear()
                            self.active = False


# -------------------- Arranque --------------------

def main():
    cfg_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    if not os.path.exists(cfg_path):
        print(f"No existe config.yaml en {cfg_path}")
        sys.exit(1)
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}

    speaker = Speaker(language_hint='es')

    plugins = load_plugins(cfg.get('plugins', []))

    listener = VoskListener(cfg)
    try:
        listener.loop(plugins, speaker)
    except KeyboardInterrupt:
        print("\nSaliendo…")


if __name__ == '__main__':
    main()