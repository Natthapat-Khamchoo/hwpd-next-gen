"""
Tests for how rows are handed to the Sheets API (unittest runner compatible).
No network — the worksheet is stubbed.
"""

import unittest
from unittest import mock

from app.core.schema import get_columns
from app.services import sheets_service


class FakeWorksheet:
    def __init__(self):
        self.appended = None
        self.value_input_option = None

    def append_row(self, values, value_input_option=None):
        self.appended = values
        self.value_input_option = value_input_option
        return {"updates": {"updatedRange": "tb_Checkpoints!A2:O2"}}


def write_row(row):
    worksheet = FakeWorksheet()
    # แคช handle ค้างจากเทสก่อนหน้าจะทำให้ได้ worksheet ผิดตัว
    sheets_service.reset_client()
    with mock.patch.object(sheets_service, "open_spreadsheet", return_value=object()), mock.patch.object(
        sheets_service, "ensure_worksheet", return_value=worksheet
    ):
        result = sheets_service.append_report_row("sheet-id", "tb_Checkpoints", row)
    sheets_service.reset_client()
    return worksheet, result


def sample_row(**overrides):
    row = ["" for _ in get_columns("tb_Checkpoints")]
    row[0] = "CHK-260726-0900-123"
    for index, value in overrides.items():
        row[int(index)] = value
    return row


class TestAppendReportRow(unittest.TestCase):
    def test_uses_raw_so_leading_zeros_survive(self):
        """
        USER_ENTERED ทำให้ Sheets อ่าน "0812345678" เป็นตัวเลขแล้วเลข 0 หน้าหาย
        ซึ่งเกิดขึ้นจริงกับข้อมูลที่ Apps Script เขียนไว้ RAW เก็บค่าตามที่ส่งไป
        """
        worksheet, _ = write_row(sample_row(**{"10": "0812345678"}))
        self.assertEqual(worksheet.value_input_option, "RAW")
        self.assertEqual(worksheet.appended[10], "0812345678")

    def test_none_becomes_empty_string(self):
        row = sample_row()
        row[11] = None
        worksheet, _ = write_row(row)
        self.assertEqual(worksheet.appended[11], "")
        self.assertNotIn(None, worksheet.appended)

    def test_reports_where_the_row_landed(self):
        _, result = write_row(sample_row())
        self.assertEqual(result["spreadsheetId"], "sheet-id")
        self.assertEqual(result["tableName"], "tb_Checkpoints")
        self.assertEqual(result["updatedRange"], "tb_Checkpoints!A2:O2")

    def test_wrong_width_is_refused_before_writing(self):
        with self.assertRaises(sheets_service.SheetWriteError) as ctx:
            write_row(["only-one-value"])
        self.assertIn("ไม่ตรงกับหัวคอลัมน์", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
