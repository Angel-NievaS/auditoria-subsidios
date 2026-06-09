# Auditoría Comprobantes de Subsidios

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
```

### Dependencia de sistema: Tesseract OCR

Necesario para el Formato 2 (comprobantes con datos en imagen).

- **Windows**: descargar instalador desde https://github.com/UB-Mannheim/tesseract/wiki
  e instalar el paquete de idioma `spa` (Spanish).
- **macOS**: `brew install tesseract tesseract-lang`
- **Debian/Ubuntu**: `sudo apt-get install tesseract-ocr tesseract-ocr-spa`

Si Tesseract no está instalado, los comprobantes de Formato 2 se marcan como
⚠️ "Revisar manualmente" y el análisis continúa sin interrupciones.

## Cómo ejecutar

```bash
flask --app app run
```

Luego abrir http://127.0.0.1:5000 en el navegador.

## Estructura

```
src/sources/      ← abstracción de fuente (LocalSource hoy, DriveSource en el futuro)
src/parsing/      ← clasificador y 4 extractores
src/domain/       ← modelos de datos + reglas de auditoría
src/services/     ← orquestación
src/export/       ← generación de Excel
templates/        ← vistas Jinja2
tests/            ← pruebas pytest (agregar PDF reales en tests/fixtures/)
```
