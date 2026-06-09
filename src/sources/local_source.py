"""LocalSource: lee comprobantes desde el sistema de archivos local."""
import re
from pathlib import Path

from .base import ReceiptFile, ReceiptSource, StudentFolder

_RTD_RE = re.compile(r"RTD[-\s]\d{2}-\d{2}-\d{2}-\d{4}-\d+", re.IGNORECASE)


def _extraer_codigo_curso(nombre: str) -> str:
    """Extrae el código RTD-XX-XX-XX-XXXX-X del nombre de carpeta; '' si no lo tiene."""
    m = _RTD_RE.search(nombre)
    if not m:
        return ""
    # Normaliza espacio a guión: "RTD 24-01-..." → "RTD-24-01-..."
    return re.sub(r"(?i)RTD\s+", "RTD-", m.group(0)).upper()


class LocalSource(ReceiptSource):
    def __init__(self, root_path: str | Path):
        self._root = Path(root_path)

    def _resolve_structure(self) -> list[tuple[str, Path]]:
        """
        Detecta la estructura de carpetas y devuelve pares (codigo_curso, ruta_alumnos).

        Casos soportados:
        A) La raíz contiene carpetas con código RTD (multi-curso o curso único cargado
           como subcarpeta): cada carpeta RTD contiene alumnos.
        B) La raíz misma tiene nombre RTD (usuario seleccionó la carpeta del curso):
           los alumnos están directamente en la raíz.
        C) Existe subcarpeta "comprobante*" (estructura heredada): alumnos dentro.
        D) Cualquier otro caso: los alumnos están en la raíz.
        """
        hijos = sorted([c for c in self._root.iterdir() if c.is_dir()])

        # Caso A: hijos son carpetas con código RTD
        con_rtd = [(c, _extraer_codigo_curso(c.name)) for c in hijos if _extraer_codigo_curso(c.name)]
        if con_rtd:
            return [(codigo, ruta) for ruta, codigo in con_rtd]

        # El código del curso es el de la raíz (si tiene) o vacío
        codigo_raiz = _extraer_codigo_curso(self._root.name)

        # Caso C: subcarpeta con "comprobante" en el nombre
        for hijo in hijos:
            if re.search(r"comprobante", hijo.name, re.IGNORECASE):
                return [(codigo_raiz, hijo)]

        # Casos B/D: los alumnos están en la raíz
        return [(codigo_raiz, self._root)]

    def list_student_folders(self) -> list[StudentFolder]:
        folders: list[StudentFolder] = []
        for codigo, ruta_alumnos in self._resolve_structure():
            # Si la carpeta del curso contiene una subcarpeta "COMPROBANTES POR ALUMNOS"
            # (o variante), los alumnos están dentro de ella
            ruta_efectiva = ruta_alumnos
            for child in sorted(ruta_alumnos.iterdir()):
                if child.is_dir() and re.search(r"comprobante", child.name, re.IGNORECASE):
                    ruta_efectiva = child
                    break
            for child in sorted(ruta_efectiva.iterdir()):
                if child.is_dir():
                    folders.append(StudentFolder(id=str(child), name=child.name, curso=codigo))
        return folders

    def list_receipts(self, folder: StudentFolder) -> list[ReceiptFile]:
        folder_path = Path(folder.id)
        receipts: list[ReceiptFile] = []

        # PDFs en la raíz de la carpeta del alumno → subsidio
        for f in sorted(folder_path.iterdir()):
            if f.is_file() and f.suffix.lower() == ".pdf":
                receipts.append(ReceiptFile(id=str(f), name=f.name, categoria="subsidio"))

        for child in sorted(folder_path.iterdir()):
            if not child.is_dir():
                continue
            if re.search(r"cuidado", child.name, re.IGNORECASE):
                # Subcarpeta CUIDADOS → cuidados
                for f in sorted(child.iterdir()):
                    if f.is_file() and f.suffix.lower() == ".pdf":
                        receipts.append(ReceiptFile(id=str(f), name=f.name, categoria="cuidados"))
            elif re.search(r"comprobante", child.name, re.IGNORECASE):
                # Subcarpeta tipo "COMPROBANTES POR ALUMNOS" → subsidio
                for f in sorted(child.iterdir()):
                    if f.is_file() and f.suffix.lower() == ".pdf":
                        receipts.append(ReceiptFile(id=str(f), name=f.name, categoria="subsidio"))

        return receipts

    def read_bytes(self, receipt: ReceiptFile) -> bytes:
        return Path(receipt.id).read_bytes()

    def link_for(self, receipt: ReceiptFile) -> str:
        return str(Path(receipt.id).resolve())
