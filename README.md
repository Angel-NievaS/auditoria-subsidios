# Auditoría de Subsidios — Talento Digital

Aplicación web local para auditar comprobantes de pago de subsidios de alumnos Talento Digital.
Procesa PDFs de liquidaciones, certificados BancoEstado y comprobantes de transferencia (OCR),
y genera un informe Excel con alertas por alumno y por curso.

---

## Descargar e instalar

> **No requiere Python, Tesseract ni ninguna otra dependencia.**

[![Descargar instalador](https://img.shields.io/badge/Descargar-Auditoria_Subsidios_v1.0_Setup.exe-blue?style=for-the-badge&logo=windows)](https://github.com/Angel-NievaS/auditoria-subsidios/releases/latest/download/Auditoria_Subsidios_v1.0_Setup.exe)

O desde la [página de releases](https://github.com/Angel-NievaS/auditoria-subsidios/releases/latest).

---

## Uso

1. Ejecutar **Auditoria Subsidios** desde el acceso directo del escritorio.
2. Se abrirá el navegador en `http://127.0.0.1:5000`.
3. Seleccionar la carpeta con los comprobantes y hacer clic en **Analizar**.
4. Al terminar, descargar el informe Excel con el botón **Exportar**.

### Estructura de carpetas esperada

```
RTD-XX-XX-XX-XXXX-X/
├── ALUMNO UNO/
│   ├── Semana1.pdf
│   └── Semana2.pdf
└── ALUMNO DOS/
    └── COMPROBANTES POR ALUMNOS/
        └── Semana1.pdf
```

---

## Formatos de comprobante soportados

| Formato | Descripción |
|---------|-------------|
| Liquidación de pago | PDF texto ~14 KB |
| Certificado BancoEstado v1 | PDF texto ~32–41 KB |
| Certificado BancoEstado v2 | PDF texto |
| Comprobante de transferencia | PDF con imagen (OCR) |

---

## Desarrollo

### Requisitos

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Tesseract OCR es necesario para comprobantes con datos en imagen:
- **Windows**: https://github.com/UB-Mannheim/tesseract/wiki (instalar paquete `spa`)

### Ejecutar en modo desarrollo

```bash
flask --app app run --debug
```

### Construir el instalador

```bash
# 1. Ejecutable PyInstaller
.venv\Scripts\pyinstaller auditoria.spec

# 2. Instalador Inno Setup
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

### Estructura del proyecto

```
src/
├── domain/       ← modelos de datos y reglas de auditoría
├── export/       ← generación de Excel
├── parsing/      ← clasificador y extractores de PDF
├── services/     ← orquestación y paralelismo
└── sources/      ← abstracción de fuente (local / Drive)
templates/        ← vistas Jinja2
tests/            ← pruebas pytest
```
