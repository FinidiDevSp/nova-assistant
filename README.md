# NOVA ASR (Vosk + Hotword + Silencio + Plugins)

Este starter project implementa dos modos:
1. **keyword_once**: dice la palabra de activación y, tras un **silencio razonable**, transcribe lo dicho y ejecuta plugins.
2. **keyword_until_stop**: transcribe de forma continua hasta detectar la palabra **stop**.

Incluye **TTS** con `pyttsx3` y plugins de **saludo**, **volumen**, **control del sistema** (apagar o hibernar el ordenador), **pantalla** (apagarla o ajustar el brillo) y un plugin de **modos** configurable.

## Requisitos
```bash
pip install -r requirements.txt
```
Descarga un modelo de Vosk (es-ES grande) desde https://alphacephei.com/vosk/models y descomprímelo en `models/es` (o ajusta `config.yaml`).

## Ejecutar
```bash
python src/main.py
```
Todos los archivos YAML residen en la carpeta `config/`. Ajusta `activation_word`, `stop_word`, `mic_off_word`, `mode`, umbral/timeout de silencio, `person_name` y las `hotkeys` en `config/config.yaml`. Los modos configurables se definen en `config/modos.yaml` y la memoria persistente se almacena en `config/memory.yaml`.
