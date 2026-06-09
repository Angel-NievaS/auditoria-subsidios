from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ReceiptFile:
    id: str    # ruta local (v1) o fileId de Drive (futuro)
    name: str  # nombre del archivo, ej: "semana19 (1).pdf"
    categoria: str = "subsidio"  # "subsidio" | "cuidados"


@dataclass
class StudentFolder:
    id: str
    name: str   # nombre del alumno (= nombre de la carpeta)
    curso: str = ""  # código RTD extraído del nombre de la carpeta padre


class ReceiptSource(ABC):
    """Fuente de comprobantes. v1: LocalSource. Futuro: DriveSource."""

    @abstractmethod
    def list_student_folders(self) -> list[StudentFolder]: ...

    @abstractmethod
    def list_receipts(self, folder: StudentFolder) -> list[ReceiptFile]:
        """Solo archivos .pdf. Ignora cualquier otro tipo."""

    @abstractmethod
    def read_bytes(self, receipt: ReceiptFile) -> bytes: ...

    @abstractmethod
    def link_for(self, receipt: ReceiptFile) -> str:
        """Referencia para revisión manual (ruta local en v1)."""
