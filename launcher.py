"""
Punto de entrada para el ejecutable generado con PyInstaller.
Configura rutas de recursos bundled, abre el navegador y lanza Flask.
"""
import os
import sys
import threading
import webbrowser

# Cuando se ejecuta como .exe, sys._MEIPASS apunta al directorio temporal
# donde PyInstaller extrae los archivos. Configuramos Tesseract antes de
# cualquier import que lo use.
if hasattr(sys, "_MEIPASS"):
    os.environ["TESSDATA_PREFIX"] = os.path.join(sys._MEIPASS, "tessdata")

PORT = 5000


def _abrir_navegador() -> None:
    import time
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{PORT}")


if __name__ == "__main__":
    threading.Thread(target=_abrir_navegador, daemon=True).start()
    from app import app
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True, use_reloader=False)
