"""
Tests for the three forms that are not a plain single-row insert:
daily-summary (HQ rollup), mission-summary (LINE only) and auto-arrest (Docs).
No network — Google is stubbed throughout.
"""

import unittest
from unittest import mock

from app.core.schema import get_columns
from app.services import docs_service
from app.services.report_service import (
    build_mission_summary,
    format_thai_datetime,
    prepare_hq_summary,
)

FAKE_ROUTER = '{"5":{"OPS":"fake-sheet-id"}}'

FORM = {
    "stationId": "51",
    "actionBy": "st51",
    "reportDateTime": "2026-07-27T08:30",
    "v43": "12",
    "service": "5",
    "v42": "2",
    "v20": "3",
    "chargesText": "ขับเร็ว = 5\nไม่สวมหมวก = 2",
}


class TestThaiDateTime(unittest.TestCase):
    def test_formats_date_and_time_in_buddhist_years(self):
        self.assertEqual(format_thai_datetime("2026-07-27T14:30"), "27 ก.ค. 69 เวลา 14.30 น.")

    def test_date_without_time_drops_the_time_clause(self):
        self.assertEqual(format_thai_datetime("2026-07-27"), "27 ก.ค. 69")

    def test_seconds_are_trimmed(self):
        self.assertEqual(format_thai_datetime("2026-01-05T09:05:33"), "5 ม.ค. 69 เวลา 09.05 น.")

    def test_blank_and_malformed_values_do_not_raise(self):
        self.assertEqual(format_thai_datetime(""), "-")
        self.assertEqual(format_thai_datetime("ไม่ใช่วันที่"), "ไม่ใช่วันที่")
        self.assertEqual(format_thai_datetime("2026-13-01"), "2026-13-01")


class TestHqSummary(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"DB_ROUTER_JSON": FAKE_ROUTER}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_row_matches_the_ten_column_schema(self):
        prepared = prepare_hq_summary(dict(FORM))
        self.assertEqual(prepared["tableName"], "tb_HQ_Summary")
        self.assertEqual(len(prepared["rowData"]), len(get_columns("tb_HQ_Summary")))

    def test_values_land_in_the_columns_the_schema_names(self):
        prepared = prepare_hq_summary(dict(FORM))
        row = dict(zip(get_columns("tb_HQ_Summary"), prepared["rowData"]))
        self.assertEqual(row["Data_StationID"], "51")
        self.assertEqual(row["Data_ReportDate"], "2026-07-27")
        self.assertEqual(row["Sum_V43"], 12)
        self.assertEqual(row["Sum_Service"], 5)
        self.assertEqual(row["Sum_V42"], 2)
        self.assertEqual(row["Sum_V20"], 3)
        self.assertEqual(row["Sys_ActionBy"], "st51")

    def test_counts_arrive_as_numbers_not_strings(self):
        row = dict(zip(get_columns("tb_HQ_Summary"), prepare_hq_summary(dict(FORM))["rowData"]))
        for column in ("Sum_V43", "Sum_Service", "Sum_V42", "Sum_V20"):
            self.assertIsInstance(row[column], int, f"{column} ควรเป็นตัวเลข")

    def test_missing_counts_become_zero_rather_than_blank(self):
        row = dict(zip(get_columns("tb_HQ_Summary"), prepare_hq_summary({"stationId": "51"})["rowData"]))
        self.assertEqual(row["Sum_V43"], 0)
        self.assertEqual(row["Sum_Charges"], "-")

    def test_record_id_carries_the_station(self):
        self.assertTrue(prepare_hq_summary(dict(FORM))["recordId"].startswith("HQ-SUM-51-"))

    def test_line_message_lists_every_figure(self):
        message = prepare_hq_summary(dict(FORM))["lineMessage"]
        for fragment in ("ว.43 = 12", "บริการ = 5", "ว.42 = 2", "ว.20 = 3", "27 ก.ค. 69"):
            self.assertIn(fragment, message)
        self.assertIn("ขับเร็ว = 5", message)

    def test_no_charges_leaves_out_the_breakdown_heading(self):
        message = prepare_hq_summary({"stationId": "51", "reportDateTime": "2026-07-27T08:00"})["lineMessage"]
        self.assertNotIn("แบ่งเป็น", message)


class TestMissionSummary(unittest.TestCase):
    MISSIONS = [
        {"startTime": "27/07/2569 09:00", "targetUnits": "คลองขลุง", "details": "คุ้มกันขบวน"},
        {"startTime": "27/07/2569 13:00", "targetUnits": "แม่สอด", "details": "ตั้งจุดตรวจ"},
    ]

    def test_writes_nothing_to_a_table(self):
        prepared = build_mission_summary({"stationId": "51", "unitName": "คลองขลุง"}, self.MISSIONS)
        self.assertNotIn("tableName", prepared)
        self.assertNotIn("rowData", prepared)

    def test_one_unit_omits_the_unit_prefix(self):
        message = build_mission_summary({"stationId": "51", "unitName": "คลองขลุง"}, self.MISSIONS)["lineMessage"]
        self.assertIn("หน่วย คลองขลุง", message)
        self.assertNotIn("[คลองขลุง]", message)

    def test_all_units_prefixes_each_line_with_its_unit(self):
        message = build_mission_summary({"stationId": "51", "unitName": "ทุกหน่วย"}, self.MISSIONS)["lineMessage"]
        self.assertIn("[คลองขลุง]", message)
        self.assertIn("[แม่สอด]", message)
        self.assertIn("สรุปภารกิจทุกหน่วย", message)

    def test_blank_unit_is_treated_as_all_units(self):
        message = build_mission_summary({"stationId": "51", "unitName": ""}, self.MISSIONS)["lineMessage"]
        self.assertIn("สรุปภารกิจทุกหน่วย", message)

    def test_no_missions_says_so_instead_of_an_empty_block(self):
        prepared = build_mission_summary({"stationId": "51", "unitName": "คลองขลุง"}, [])
        self.assertIn("ไม่มีภารกิจในช่วงเวลาดังกล่าว", prepared["lineMessage"])
        self.assertEqual(prepared["missionCount"], 0)

    def test_non_dict_entries_are_skipped(self):
        prepared = build_mission_summary({"stationId": "51"}, ["ขยะ", None, self.MISSIONS[0]])
        self.assertEqual(prepared["missionCount"], 1)

    def test_dates_are_shown_in_buddhist_years(self):
        message = build_mission_summary(
            {"stationId": "51", "startDate": "2026-07-01", "endDate": "2026-07-31"}, []
        )["lineMessage"]
        self.assertIn("01/07/2569", message)
        self.assertIn("31/07/2569", message)


class TestAutoArrestConfiguration(unittest.TestCase):
    def test_reports_missing_template_ids_rather_than_failing_obscurely(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            for key in ("AUTO_ARREST_DOC_ID", "AUTO_ARREST_M22_ID", "AUTO_ARREST_FOLDER_ID"):
                docs_service.os.environ.pop(key, None)
            self.assertFalse(docs_service.is_configured())
            with self.assertRaises(docs_service.TemplateNotConfigured) as ctx:
                docs_service.generate_arrest_documents({}, [{"name": "ก"}])
            self.assertIn("AUTO_ARREST_DOC_ID", str(ctx.exception))

    def test_partial_configuration_still_counts_as_unconfigured(self):
        with mock.patch.dict("os.environ", {"AUTO_ARREST_DOC_ID": "x"}, clear=False):
            for key in ("AUTO_ARREST_M22_ID", "AUTO_ARREST_FOLDER_ID"):
                docs_service.os.environ.pop(key, None)
            self.assertFalse(docs_service.is_configured())


class TestAutoArrestGeneration(unittest.TestCase):
    ENV = {
        "AUTO_ARREST_DOC_ID": "template-main",
        "AUTO_ARREST_M22_ID": "template-m22",
        "AUTO_ARREST_FOLDER_ID": "folder-1",
    }

    FORM = {
        "recordDate": "2026-07-27T10:00",
        "arrestDate": "2026-07-26T22:15",
        "offense": "ยาเสพติด",
        "arrestLocation": "ทล.1 กม.50",
        "detentionLocation": "ส.ทล.1 กก.5",
        "circumstances": "พฤติการณ์",
        "briefCircumstances": "ย่อ",
        "allSuspectsText": "1. นาย ก",
        "respOfficer": "ร.ต.อ. ผู้รับผิดชอบ",
        "respPhone": "0811111111",
        "notifyOfficer": "ด.ต. ผู้แจ้ง",
        "notifyPhone": "0822222222",
    }

    def _run(self, form=None, suspects=None):
        drive, docs = mock.Mock(), mock.Mock()
        copied = []

        def fake_copy(fileId=None, body=None, fields=None, supportsAllDrives=None):
            copied.append((fileId, body["name"]))
            result = mock.Mock()
            result.execute.return_value = {"id": f"doc-{len(copied)}"}
            return result

        drive.files.return_value.copy.side_effect = fake_copy
        docs.documents.return_value.batchUpdate.return_value.execute.return_value = {}

        with mock.patch.dict("os.environ", self.ENV, clear=False), \
             mock.patch.object(docs_service.sheets_service, "is_configured", return_value=True), \
             mock.patch.object(docs_service, "_services", return_value=(drive, docs)):
            links = docs_service.generate_arrest_documents(
                form if form is not None else dict(self.FORM),
                suspects if suspects is not None else [
                    {"name": "นาย ก", "idCard": "1", "nat": "ไทย", "age": "30", "address": "x", "phone": "08"},
                    {"name": "นาย ข", "idCard": "2", "nat": "ลาว", "age": "25", "address": "y", "phone": "09"},
                ],
            )
        return links, copied, docs

    def test_makes_one_main_document_plus_one_per_suspect(self):
        links, copied, _ = self._run()
        self.assertEqual(len(links), 3)
        self.assertEqual(links[0]["name"], "บันทึกจับกุม (รวมทุกคน)")
        self.assertEqual([l["name"] for l in links[1:]], ["ม.22,23 ของ นาย ก", "ม.22,23 ของ นาย ข"])
        self.assertEqual([template for template, _ in copied],
                         ["template-main", "template-m22", "template-m22"])

    def test_copies_land_in_the_configured_folder(self):
        drive, docs = mock.Mock(), mock.Mock()
        drive.files.return_value.copy.return_value.execute.return_value = {"id": "doc-1"}
        docs.documents.return_value.batchUpdate.return_value.execute.return_value = {}
        with mock.patch.dict("os.environ", self.ENV, clear=False), \
             mock.patch.object(docs_service.sheets_service, "is_configured", return_value=True), \
             mock.patch.object(docs_service, "_services", return_value=(drive, docs)):
            docs_service.generate_arrest_documents(dict(self.FORM), [{"name": "นาย ก"}])
        self.assertEqual(drive.files.return_value.copy.call_args.kwargs["body"]["parents"], ["folder-1"])

    def test_links_are_docx_export_urls(self):
        links, _, _ = self._run()
        for link in links:
            self.assertTrue(link["url"].endswith("/export?format=docx"), link["url"])

    def test_short_officer_field_names_from_the_form_reach_the_template(self):
        """ฟอร์มส่ง respOfficer แต่แม่แบบใช้ตัวยึด RESPONSIBLE_OFFICER_NAME"""
        _, _, docs = self._run()
        first_call = docs.documents.return_value.batchUpdate.call_args_list[0]
        replacements = {
            r["replaceAllText"]["containsText"]["text"]: r["replaceAllText"]["replaceText"]
            for r in first_call.kwargs["body"]["requests"]
        }
        self.assertEqual(replacements["<<RESPONSIBLE_OFFICER_NAME>>"], "ร.ต.อ. ผู้รับผิดชอบ")
        self.assertEqual(replacements["<<NOTIFYING_OFFICER_PHONE>>"], "0822222222")

    def test_long_officer_field_names_win_when_both_are_sent(self):
        form = dict(self.FORM, respOfficerName="ชื่อยาว")
        _, _, docs = self._run(form=form)
        first_call = docs.documents.return_value.batchUpdate.call_args_list[0]
        replacements = {
            r["replaceAllText"]["containsText"]["text"]: r["replaceAllText"]["replaceText"]
            for r in first_call.kwargs["body"]["requests"]
        }
        self.assertEqual(replacements["<<RESPONSIBLE_OFFICER_NAME>>"], "ชื่อยาว")

    def test_dates_reach_the_template_in_thai(self):
        _, _, docs = self._run()
        first_call = docs.documents.return_value.batchUpdate.call_args_list[0]
        replacements = {
            r["replaceAllText"]["containsText"]["text"]: r["replaceAllText"]["replaceText"]
            for r in first_call.kwargs["body"]["requests"]
        }
        self.assertEqual(replacements["<<ARREST_DATE>>"], "26 ก.ค. 69 เวลา 22.15 น.")

    def test_blank_fields_are_still_replaced_so_no_placeholder_survives(self):
        _, _, docs = self._run(form={"arrestDate": "2026-07-26T22:15"})
        first_call = docs.documents.return_value.batchUpdate.call_args_list[0]
        replacements = {
            r["replaceAllText"]["containsText"]["text"]: r["replaceAllText"]["replaceText"]
            for r in first_call.kwargs["body"]["requests"]
        }
        self.assertEqual(replacements["<<OFFENSE>>"], "")
        self.assertIn("<<CIRCUMSTANCES>>", replacements)

    def test_suspects_without_a_name_are_skipped(self):
        links, copied, _ = self._run(suspects=[{"name": "  "}, {"idCard": "1"}, {"name": "นาย ก"}])
        self.assertEqual(len(links), 2)
        self.assertEqual(len(copied), 2)

    def _failing(self, side_effect):
        drive, docs = mock.Mock(), mock.Mock()
        drive.files.return_value.copy.return_value.execute.return_value = {"id": "doc-1"}
        docs.documents.return_value.batchUpdate.side_effect = side_effect
        with mock.patch.dict("os.environ", self.ENV, clear=False), \
             mock.patch.object(docs_service.sheets_service, "is_configured", return_value=True), \
             mock.patch.object(docs_service, "_services", return_value=(drive, docs)):
            with self.assertRaises(docs_service.DocumentError) as ctx:
                docs_service.generate_arrest_documents(dict(self.FORM), [{"name": "นาย ก"}])
        return ctx.exception, drive

    def test_a_failure_partway_reports_what_was_already_made(self):
        error, _ = self._failing([mock.Mock(**{"execute.return_value": {}}), RuntimeError("Docs API ล่ม")])
        self.assertIn("บันทึกจับกุม (รวมทุกคน)", str(error))

    def test_the_half_filled_copy_is_deleted(self):
        """
        สำเนาถูกสร้างก่อนแล้วค่อยแทนที่ข้อความ ถ้าขั้นที่สองล้ม จะเหลือเอกสารที่
        ตัวยึด <<OFFENSE>> ยังค้างอยู่ปนกับฉบับที่ใช้ได้จริง
        """
        _, drive = self._failing(RuntimeError("Docs API ล่ม"))
        drive.files.return_value.delete.assert_called_once()
        self.assertEqual(drive.files.return_value.delete.call_args.kwargs["fileId"], "doc-1")

    def test_a_disabled_docs_api_is_explained_not_dumped(self):
        raw = RuntimeError(
            'returned "Google Docs API has not been used in project 123 before or it is '
            'disabled." reason: SERVICE_DISABLED service: docs.googleapis.com'
        )
        error, _ = self._failing(raw)
        self.assertIn("ยังไม่ได้เปิดใช้งาน Google Docs API", str(error))
        self.assertIn("console.cloud.google.com", str(error))
        self.assertNotIn("SERVICE_DISABLED", str(error))

    def test_a_missing_template_is_explained(self):
        error, _ = self._failing(RuntimeError('HttpError 404 ... "notFound"'))
        self.assertIn("AUTO_ARREST_DOC_ID", str(error))

    def test_a_permission_problem_is_explained(self):
        error, _ = self._failing(RuntimeError('HttpError 403 ... "insufficientPermissions"'))
        self.assertIn("สิทธิ์แก้ไขแม่แบบ", str(error))

    def test_a_failed_delete_does_not_mask_the_original_error(self):
        drive, docs = mock.Mock(), mock.Mock()
        drive.files.return_value.copy.return_value.execute.return_value = {"id": "doc-1"}
        drive.files.return_value.delete.side_effect = RuntimeError("ลบไม่ได้")
        docs.documents.return_value.batchUpdate.side_effect = RuntimeError("Docs API ล่ม")
        with mock.patch.dict("os.environ", self.ENV, clear=False), \
             mock.patch.object(docs_service.sheets_service, "is_configured", return_value=True), \
             mock.patch.object(docs_service, "_services", return_value=(drive, docs)):
            with self.assertRaises(docs_service.DocumentError) as ctx:
                docs_service.generate_arrest_documents(dict(self.FORM), [{"name": "นาย ก"}])
        self.assertIn("Docs API ล่ม", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
