"""Grava séries extensas em Excel sem materializar todas as células na memória."""

from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
import pandas


import os
import tempfile


def write_frames(path, sheets):
    workbook = Workbook(write_only=True)
    for name, frame in sheets:
        sheet = workbook.create_sheet(name)
        header = []
        for column in frame.columns:
            cell = WriteOnlyCell(sheet, value=column)
            cell.font = Font(bold=True)
            header.append(cell)
        sheet.append(header)
        for row in frame.itertuples(index=False, name=None):
            sheet.append([
                None if pandas.isna(value) else
                value.to_pydatetime() if isinstance(value, pandas.Timestamp) else
                value.item() if hasattr(value, "item") and not isinstance(value, (date, datetime)) else value
                for value in row
            ])
    # Grava primeiro em arquivo temporário no mesmo diretório e renomeia
    # atomicamente; evita deixar um .xlsx truncado/corrompido (BadZipFile) se o
    # processo for interrompido antes do término da compactação.
    target_dir = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_write_", suffix=".xlsx", dir=target_dir)
    os.close(fd)
    try:
        workbook.save(tmp_path)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

