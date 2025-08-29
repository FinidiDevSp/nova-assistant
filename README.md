# NOVA ASR (Vosk + Hotword + Silencio + Plugins)

Este starter project implementa dos modos:
1. **keyword_once**: dice la palabra de activación y, tras un **silencio razonable**, transcribe lo dicho y ejecuta plugins.
2. **keyword_until_stop**: transcribe de forma continua hasta detectar la palabra **stop**.

Incluye **TTS** con `pyttsx3` y un plugin de **saludo** (palabra clave: `saludame`).

## Requisitos
```bash
pip install -r requirements.txt
```
Descarga un modelo de Vosk (es-ES grande) desde https://alphacephei.com/vosk/models y descomprímelo en `models/es` (o ajusta `config.yaml`).

## Ejecutar
```bash
python main.py
```
Ajusta `activation_word`, `stop_word`, `mode`, umbral/timeout de silencio y `person_name` en `config.yaml`.