"""DriveSource: TODO - implementar cuando se migre a Google Drive.

Debe heredar de ReceiptSource e implementar los 4 métodos abstractos
leyendo de la API de Google Drive en vez del sistema de archivos local.
"""
from .base import ReceiptFile, ReceiptSource, StudentFolder


class DriveSource(ReceiptSource):
    # TODO: implementar con google-api-python-client
    def list_student_folders(self) -> list[StudentFolder]: raise NotImplementedError
    def list_receipts(self, folder: StudentFolder) -> list[ReceiptFile]: raise NotImplementedError
    def read_bytes(self, receipt: ReceiptFile) -> bytes: raise NotImplementedError
    def link_for(self, receipt: ReceiptFile) -> str: raise NotImplementedError
