"""
จัดกลุ่มฐานความผิดตาม พ.ร.บ. (requirement ข้อ 14)

จุดที่ต้องระวัง: การเดากลุ่มจากคำในชื่อข้อหาเป็นแค่ตัวช่วยชั่วคราว ไม่ใช่คำตอบ
ทางกฎหมาย เทสชุดนี้จึงยืนยันสองอย่าง — ค่าที่คนกรอกในชีตต้องชนะการเดาเสมอ
และข้อหาที่เดาไม่ได้ต้องตกไป "ข้อหาเฉพาะทาง" ไม่ใช่ถูกยัดเข้ากลุ่มใดกลุ่มหนึ่ง
"""

import unittest
from unittest import mock

from app.services import charge_group_service as cg
from app.services import reference_service


class TestGuessing(unittest.TestCase):
    def test_keywords_map_to_the_four_acts(self):
        cases = [
            ("บรรทุกน้ำหนักเกินอัตราที่กฎหมายกำหนด", cg.ACT_HIGHWAY),
            ("ใช้รถขนส่งไม่ประจำทางโดยไม่ได้รับอนุญาต", cg.ACT_LAND_TRANSPORT),
            ("ใช้ป้ายทะเบียนปลอม", cg.ACT_VEHICLE),
            ("ขับรถเร็วเกินกว่าที่กฎหมายกำหนด", cg.ACT_TRAFFIC),
            ("เมาแล้วขับ", cg.ACT_TRAFFIC),
        ]
        for name, expected in cases:
            self.assertEqual(cg.guess_group(name), expected, name)

    def test_anything_unrecognised_falls_into_the_special_group(self):
        # ตกกลุ่มเฉพาะทางปลอดภัยกว่าเดาผิดกลุ่ม เพราะคนอ่านจะเห็นว่ายังไม่ได้จัด
        for name in ("ยาเสพติดให้โทษประเภท 1", "พาอาวุธปืนไปในเมือง", ""):
            self.assertEqual(cg.guess_group(name), cg.GROUP_SPECIAL, name)

    def test_the_more_specific_act_wins_over_the_general_one(self):
        # "รถขนส่ง" ต้องไม่ถูก พ.ร.บ.รถยนต์ คว้าไปเพราะมีคำว่า "รถ"
        self.assertEqual(cg.guess_group("ขับรถขนส่งโดยไม่มีใบอนุญาตขับรถขนส่ง"), cg.ACT_LAND_TRANSPORT)


class TestSheetValueWins(unittest.TestCase):
    def test_a_value_typed_in_the_sheet_overrides_the_guess(self):
        # ชื่อนี้เดาได้ว่าเป็นจราจร แต่ถ้าฝ่ายกฎหมายระบุว่าเป็นทางหลวง ต้องเชื่อคน
        self.assertEqual(cg.group_of("ขับเร็วในเขตทาง", "พ.ร.บ.ทางหลวง"), cg.ACT_HIGHWAY)

    def test_shorthand_typed_by_staff_is_accepted(self):
        for typed in ("จราจรทางบก", "พ.ร.บ.จราจรทางบก", " จราจรทางบก "):
            self.assertEqual(cg.normalize_group(typed), cg.ACT_TRAFFIC, typed)

    def test_an_unrecognised_group_name_falls_back_to_guessing(self):
        self.assertEqual(cg.group_of("ขับรถเร็วเกินกำหนด", "พ.ร.บ.ที่ไม่มีจริง"), cg.ACT_TRAFFIC)

    def test_a_blank_sheet_value_falls_back_to_guessing(self):
        self.assertEqual(cg.group_of("ใช้ป้ายทะเบียนปลอม", ""), cg.ACT_VEHICLE)


class TestGrouping(unittest.TestCase):
    def test_groups_come_back_in_the_order_the_unit_asked_for(self):
        charges = [
            {"name": "ก", "group": cg.GROUP_SPECIAL},
            {"name": "ข", "group": cg.ACT_TRAFFIC},
            {"name": "ค", "group": cg.ACT_HIGHWAY},
        ]
        self.assertEqual(
            [g["group"] for g in cg.grouped(charges)],
            [cg.ACT_HIGHWAY, cg.ACT_TRAFFIC, cg.GROUP_SPECIAL],
        )

    def test_empty_groups_are_not_returned(self):
        grouped = cg.grouped([{"name": "ก", "group": cg.ACT_TRAFFIC}])
        self.assertEqual([g["group"] for g in grouped], [cg.ACT_TRAFFIC])

    def test_the_five_groups_are_exactly_what_the_requirement_lists(self):
        self.assertEqual(
            cg.GROUP_ORDER,
            ["พ.ร.บ.ทางหลวง", "พ.ร.บ.ขนส่งทางบก", "พ.ร.บ.รถยนต์", "พ.ร.บ.จราจรทางบก", "ข้อหาเฉพาะทาง"],
        )


class TestChargeReading(unittest.TestCase):
    HEADER = ["ชื่อข้อหา", "b", "c", "d", "isActive", "กลุ่ม พ.ร.บ."]

    def setUp(self):
        reference_service.reset_cache()
        self.addCleanup(reference_service.reset_cache)

    def read(self, rows):
        with mock.patch.object(reference_service.sheets_service, "read_table", return_value=rows):
            return reference_service.get_charges_detailed(force=True)

    def test_the_group_column_is_read_from_the_sheet(self):
        rows = [self.HEADER, ["ขับเร็วในเขตทาง", "", "", "", "", "พ.ร.บ.ทางหลวง"]]
        self.assertEqual(self.read(rows)[0]["group"], cg.ACT_HIGHWAY)

    def test_sheets_without_the_group_column_still_work(self):
        # ชีตเดิมมีแค่ 5 คอลัมน์ ต้องอ่านได้โดยไม่ IndexError
        rows = [self.HEADER[:5], ["ขับรถเร็วเกินกว่าที่กฎหมายกำหนด", "", "", "", ""]]
        self.assertEqual(self.read(rows)[0]["group"], cg.ACT_TRAFFIC)

    def test_the_required_new_charge_is_present_even_when_the_sheet_lacks_it(self):
        names = [c["name"] for c in self.read([self.HEADER])]
        self.assertIn("บุคคลต่างด้าว (ที่เกี่ยวกับ Scammer)", names)

    def test_the_required_new_charge_is_not_duplicated_once_added_to_the_sheet(self):
        rows = [self.HEADER, ["บุคคลต่างด้าว (ที่เกี่ยวกับ Scammer)", "", "", "", "", ""]]
        names = [c["name"] for c in self.read(rows)]
        self.assertEqual(names.count("บุคคลต่างด้าว (ที่เกี่ยวกับ Scammer)"), 1)

    def test_the_plain_name_list_keeps_its_old_shape(self):
        # ฟอร์มเดิมทั้งหมดเรียก get_charges() และคาดหวังลิสต์ของสตริง
        rows = [self.HEADER, ["ขับรถเร็วเกินกว่าที่กฎหมายกำหนด", "", "", "", "", ""]]
        with mock.patch.object(reference_service.sheets_service, "read_table", return_value=rows):
            flat = reference_service.get_charges(force=True)
        self.assertTrue(all(isinstance(name, str) for name in flat))


if __name__ == "__main__":
    unittest.main()
