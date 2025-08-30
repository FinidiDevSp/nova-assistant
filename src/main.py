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
import threading
import queue
import yaml
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import pyttsx3
from datetime import datetime
from zoneinfo import ZoneInfo
import keyboard
import logging

from memory import MemoryStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

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
        """Cola y hilo dedicado para sintetizar voz.

        Se crea el motor de ``pyttsx3`` dentro del propio hilo para evitar
        problemas de inicialización con backends como ``espeak`` que solo
        funcionaban en la primera llamada cuando el motor se instanciaba en
        un hilo diferente.
        """
        self.language_hint = language_hint
        self.q = queue.Queue()
        self._on_start = None
        self._on_end = None

        # Hilo dedicado al TTS
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def set_hooks(self, on_start=None, on_end=None):
        self._on_start = on_start
        self._on_end = on_end

    def _loop(self):
        engine = pyttsx3.init()
        try:
            for v in engine.getProperty('voices'):
                name = (v.name or "").lower()
                lang = "".join(getattr(v, 'languages', []) or []).lower()
                if self.language_hint in name or self.language_hint in lang:
                    engine.setProperty('voice', v.id)
                    break
        except Exception:
            pass

        self.engine = engine
        while True:
            text = self.q.get()
            if text is None:
                break
            if self._on_start:
                self._on_start()
            try:
                engine.say(text)
                engine.runAndWait()
            finally:
                if self._on_end:
                    self._on_end()
        engine.stop()

    def say(self, text: str):
        """Encola texto para hablar (no bloquea)."""
        self.q.put(text)

    def stop(self):
        self.q.put(None)
        self.thread.join(timeout=1.0)

# -------------------- Plugins --------------------

@dataclass
class PluginCtx:
    config: Dict[str, Any]
    speak: Callable[[str], None]
    memory: MemoryStore
    config_dir: pathlib.Path


def load_plugins(plugin_names: List[str]) -> List[Any]:
    plugins = []
    for name in plugin_names:
        module_name = f"plugins.{name}"
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, 'Plugin'):
                plugins.append(module.Plugin())
                logger.info(f"[Plugins] Cargado: {name}")
            else:
                logger.warning(f"[Plugins] Aviso: {name} no expone clase Plugin")
        except Exception as e:
            logger.error(f"[Plugins] Error cargando {name}: {e}")
    return plugins


def run_plugins(plugins: List[Any], text: str, ctx: PluginCtx):
    """Ejecuta plugins cuyo matcher devuelva True para el texto dado."""
    for p in plugins:
        try:
            if p.match(text, ctx.config):
                p.run(text, ctx)
        except Exception as e:
            logger.error(f"[Plugins] Error en {getattr(p,'name','<plugin>')}: {e}")
    ctx.memory.add_history(text)


# -------------------- Reconocimiento --------------------

class VoskListener:
    def __init__(self, cfg):
        self.cfg = cfg

        # 1) Elegir dispositivo de entrada y tasa de muestreo reales
        wanted_rate = int(cfg.get('sample_rate', 16000))
        dev_info = sd.query_devices(kind='input')  # predeterminado de entrada
        device_index = cfg.get('audio_device_index', None)  # opcional en config
        if device_index is not None:
            dev_info = sd.query_devices(device_index, 'input')

        device_rate = int(dev_info['default_samplerate']) or wanted_rate
        self.device_index = device_index
        self.sample_rate = device_rate   # usa la tasa REAL del dispositivo
        logger.info(f"[Audio] Usando dispositivo: {dev_info['name']} @ {self.sample_rate} Hz (idx={self.device_index})")

        # 2) Cargar modelo correcto
        model_path = self.cfg['model_path']
        if not pathlib.Path(model_path).exists():
            logger.error(f"Modelo no encontrado en {model_path}")
            sys.exit(1)
        logger.info("Cargando modelo Vosk…")
        self.model = Model(model_path)

        # 3) Configurar recognizer con la MISMA tasa que el stream
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
        self.recognizer.SetWords(True)

        # 4) Estado
        self.q = queue.Queue()
        self.activation = cfg.get('activation_word', 'activar').lower()
        self.stop_word  = cfg.get('stop_word', 'parar').lower()
        self.mic_off_word = cfg.get('mic_off_word', 'silencio').lower()
        self.micro_enabled = True
        self.mode = cfg.get('mode', 'keyword_once')
        self.silence_timeout = float(cfg.get('silence_timeout_sec', 1.2))
        self.energy_thresh   = float(cfg.get('silence_energy_threshold', 650))

        # Ventana de silencio (None = no estamos en silencio)
        self.silence_start_ts = None

        self.active = False
        self.utterance_buffer: List[str] = []

        # 5) Calibración automática del umbral (opcional)
        if bool(cfg.get("auto_calibrate_silence", True)):
            self.energy_thresh = float(self._calibrate_noise_floor(
                seconds=float(cfg.get("calib_seconds", 1.5)),
                factor=float(cfg.get("calib_factor", 1.6)),
                min_thresh=int(cfg.get("calib_min_thresh", 120)),
            ))
        logger.info(f"[VAD] Umbral silencio: {self.energy_thresh:.1f}  Timeout: {self.silence_timeout:.2f}s")

    def _calibrate_noise_floor(self, seconds: float = 1.5, factor: float = 1.6, min_thresh: int = 120) -> float:
        """Escucha ambiente y calcula umbral de silencio recomendado."""
        import time
        samples: List[bytes] = []
        logger.info(f"[Cal] Calibrando ruido de fondo {seconds:.1f}s… mantén silencio.")
        def cb(indata, frames, time_info, status):
            if status:
                logger.debug("[SD-Cal] %s", status)
            samples.append(bytes(indata))

        block = int(self.sample_rate * 0.05)  # ~50ms
        with sd.RawInputStream(samplerate=self.sample_rate, blocksize=block,
                               dtype='int16', channels=1, callback=cb, device=self.device_index):
            t0 = time.time()
            while (time.time() - t0) < seconds:
                sd.sleep(50)

        vals = [rms_energy_int16(b) for b in samples if b]
        base = sum(vals)/len(vals) if vals else 0.0
        th = max(min_thresh, base * factor)
        logger.info(f"[Cal] Base={base:.1f}  =>  energy_thresh={th:.1f}")
        return th

    def _cb(self, indata, frames, time_info, status):
        if status:
            logger.debug("[SD] %s", status)
        self.q.put(bytes(indata))

    def _open_stream(self):
        # Usa la tasa REAL y mono. Bloque ~50ms para buenos parciales.
        return sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=int(self.sample_rate * 0.05),  # ~50 ms
            dtype='int16',
            channels=1,
            callback=self._cb,
            device=self.device_index
        )

    def disable_micro(self):
        self.micro_enabled = False
        self.active = False
        self.utterance_buffer.clear()
        self.recognizer.Reset()
        logger.info("[Micro] Desactivado")

    def enable_micro(self):
        self.micro_enabled = True
        self.recognizer.Reset()
        logger.info("[Micro] Activado")

    def _handle_final_result(self, res_json: str) -> str:
        return (json.loads(res_json).get('text') or '').strip()

    def _maybe_end_utterance(self, energy: float, now_ts: float) -> bool:
        """
        True si llevamos suficiente tiempo en silencio continuo.
        Usa RMS comparado con umbral y timeout.
        """
        # Debug opcional de energía (exporta NOVA_DEBUG_ENERGY=1)
        if os.environ.get("NOVA_DEBUG_ENERGY") == "1":
            logger.debug(f"[ENERGY] {energy:.1f}  (th={self.energy_thresh:.1f}, active={self.active}, mode={self.mode})")

        if energy < self.energy_thresh:
            if self.silence_start_ts is None:
                self.silence_start_ts = now_ts  # empezamos a contar silencio
            else:
                if (now_ts - self.silence_start_ts) >= self.silence_timeout:
                    self.silence_start_ts = None
                    return True
            return False

        # hay voz/ruido por encima del umbral: cancelar silencio
        self.silence_start_ts = None
        return False

    def loop(self, plugins, speaker: Speaker, memory: MemoryStore, config_dir: pathlib.Path):
        logger.info("Escuchando… (Ctrl+C para salir)")
        ctx = PluginCtx(config=self.cfg, speak=speaker.say, memory=memory, config_dir=config_dir)
        with self._open_stream():
            while True:
                data: bytes = self.q.get()
                if not self.micro_enabled:
                    continue
                energy = rms_energy_int16(data)
                now_ts = time.time()

                # ¿Parcial o final?
                if not self.recognizer.AcceptWaveform(data):
                    partial = (json.loads(self.recognizer.PartialResult()).get('partial') or '').lower()

                    # Debug opcional de parciales
                    # if partial: print(f"[Parcial] {partial}")

                    # Hotword en parciales
                    if not self.active and partial and self.activation in partial:
                        self.active = True
                        self.utterance_buffer.clear()
                        logger.info(f"[Hotword] Activación detectada (parcial): '{self.activation}'")
                        if self.mode == 'keyword_until_stop':
                            logger.info("[Modo] Transcripción continua hasta 'stop_word'")
                        continue

                    if self.active and self.mode == 'keyword_until_stop' and partial:
                        if self.stop_word in partial:
                            logger.info(f"[Hotword] Parada detectada (parcial): '{self.stop_word}'")
                            self.active = False
                            self.utterance_buffer.clear()
                            continue

                    # En keyword_once, si estamos activos pero no llegan finales, vigilar silencio
                    if self.active and self.mode == 'keyword_once':
                        if self._maybe_end_utterance(energy, now_ts):
                            if self.utterance_buffer:
                                utterance = " ".join(self.utterance_buffer)
                                logger.info(f"[ASR-ONCE] {utterance}")
                                run_plugins(plugins, utterance, ctx)
                            else:
                                logger.info("[ASR-ONCE] (silencio, nada que transcribir)")
                            self.utterance_buffer.clear()
                            self.active = False
                    continue

                # Final
                text = self._handle_final_result(self.recognizer.Result()).lower()
                if text:
                    logger.info(f"[Final] {text}")
                    if self.mic_off_word in text:
                        ctx.memory.add_history(text)
                        self.disable_micro()
                        speaker.say("Micrófono desactivado")
                        continue
                else:
                    # Final vacío: sirve para ayudar al VAD si estamos activos
                    if self.active and self.mode == 'keyword_once':
                        if self._maybe_end_utterance(energy, now_ts):
                            if self.utterance_buffer:
                                utterance = " ".join(self.utterance_buffer)
                                logger.info(f"[ASR-ONCE] {utterance}")
                                run_plugins(plugins, utterance, ctx)
                            else:
                                logger.info("[ASR-ONCE] (silencio, nada que transcribir)")
                            self.utterance_buffer.clear()
                            self.active = False
                    continue

                # Gestión de hotword/stop y transcripción según modo
                if not self.active:
                    if self.activation in text:
                        self.active = True
                        self.utterance_buffer.clear()
                        logger.info(f"[Hotword] Activación detectada: '{self.activation}'")
                        if self.mode == 'keyword_until_stop':
                            logger.info("[Modo] Transcripción continua hasta 'stop_word'")
                    continue

                if self.mode == 'keyword_until_stop':
                    if self.stop_word in text:
                        logger.info(f"[Hotword] Parada detectada: '{self.stop_word}'")
                        self.active = False
                        self.utterance_buffer.clear()
                        continue
                    # Ejecuta plugins en cada final mientras está activo
                    run_plugins(plugins, text, ctx)
                else:
                    # keyword_once: acumulamos hasta silencio y cortamos
                    self.utterance_buffer.append(text)
                    self.silence_start_ts = None  # hubo voz -> cancelar conteo de silencio
                    if self._maybe_end_utterance(energy, now_ts):
                        utterance = " ".join(self.utterance_buffer)
                        logger.info(f"[ASR-ONCE] {utterance}")
                        run_plugins(plugins, utterance, ctx)
                        self.utterance_buffer.clear()
                        self.active = False


# -------------------- Arranque --------------------

class Speaker(Speaker):  # alias para tipado en loop
    pass

def main():
    cfg_dir = pathlib.Path(__file__).resolve().parent.parent / 'config'
    cfg_path = cfg_dir / 'config.yaml'
    if not cfg_path.exists():
        logger.error(f"No existe config.yaml en {cfg_path}")
        sys.exit(1)
    with cfg_path.open('r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f) or {}
    memory = MemoryStore(cfg_dir / 'memory.yaml')
    history = memory.get_history()
    if history:
        logger.info(f"[Mem] Última frase: {history[-1]}")

    # (Opcional) Lista dispositivos
    if cfg.get("list_devices", False):
        logger.info("==== Dispositivos de audio ====")
        for i, d in enumerate(sd.query_devices()):
            logger.info(f"{i} {d['name']} IN= {d['max_input_channels']} OUT= {d['max_output_channels']}")
        logger.info("===============================")

    speaker = Speaker(language_hint='es')
    plugins = load_plugins(cfg.get('plugins', []))

    listener = VoskListener(cfg)

    hk = cfg.get('hotkeys', {})
    if hk.get('mic_off'):
        keyboard.add_hotkey(hk['mic_off'], listener.disable_micro)
    if hk.get('mic_on'):
        keyboard.add_hotkey(hk['mic_on'], listener.enable_micro)

    try:
        listener.loop(plugins, speaker, memory, cfg_dir)
    except KeyboardInterrupt:
        logger.info("\nSaliendo…")


if __name__ == '__main__':
    main()
