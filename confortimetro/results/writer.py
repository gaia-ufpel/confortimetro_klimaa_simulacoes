"""Grava séries extensas em Excel sem materializar todas as células na memória."""

from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
import pandas


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
    workbook.save(path)
