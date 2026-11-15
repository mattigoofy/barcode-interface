# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.tests.common import TransactionCase


class TestQuickScan(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.QuickScan = cls.env["stock.scrap.quick.scan"]
        cls.Quant = cls.env["stock.quant"]
        cls.location = cls.env["stock.location"].create(
            {
                "name": "Quick Scan Shelf",
                "usage": "internal",
                "location_id": cls.env.ref("stock.stock_location_stock").id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Quick Untracked", "is_storable": True, "barcode": "QS0001"}
        )
        cls.reason = cls.env["stock.scrap.reason.tag"].create({"name": "Broken"})

    def _qty(self):
        return self.product.with_context(location=self.location.id).qty_available

    def _quick_scan(self, **vals):
        return self.QuickScan.create(
            {"location_id": self.location.id, "product_id": self.product.id, **vals}
        )

    def test_defaults_remembered(self):
        first = self.QuickScan.create({})
        self.assertTrue(first.location_id)
        self.assertTrue(first.scrap_location_id)
        first.write(
            {
                "mode": "stock",
                "location_id": self.location.id,
                "scrap_reason_tag_ids": [(6, 0, self.reason.ids)],
            }
        )
        second = self.QuickScan.create({})
        self.assertEqual(second.mode, "stock")
        self.assertEqual(second.location_id, self.location)
        self.assertEqual(second.scrap_reason_tag_ids, self.reason)

    def test_scan_shows_then_counts_up(self):
        self.Quant._update_available_quantity(self.product, self.location, 5)
        with Form(self.QuickScan.with_context(default_location_id=self.location.id)) as form:
            form._barcode_scanned = "QS0001"
            self.assertEqual(form.product_id, self.product)
            self.assertEqual(form.qty, 1)
            self.assertEqual(form.on_hand, 5)
            form._barcode_scanned = "QS0001"
            self.assertEqual(form.qty, 2)
            self.assertEqual(form.on_hand_after, 3)

    def test_scrap(self):
        self.Quant._update_available_quantity(self.product, self.location, 3)
        quick_scan = self._quick_scan(qty=2, scrap_reason_tag_ids=[(6, 0, self.reason.ids)])
        quick_scan.action_confirm()
        self.assertFalse(quick_scan.product_id)
        self.assertEqual(quick_scan.qty, 1)
        line = quick_scan.line_ids
        self.assertEqual(line.state, "scrapped")
        self.assertEqual(line.on_hand_after, 1)
        scrap = line.move_id.scrap_id
        self.assertEqual(scrap.state, "done")
        self.assertEqual(scrap.scrap_reason_tag_ids, self.reason)
        self.assertEqual(self._qty(), 1)

    def test_scrap_more_than_in_stock(self):
        quick_scan = self._quick_scan()
        quick_scan.action_confirm()
        self.assertEqual(self._qty(), -1)

    def test_add_stock_keeps_a_count_in_progress(self):
        self.Quant._update_available_quantity(self.product, self.location, 5)
        quant = self.Quant._gather(self.product, self.location)
        quant.inventory_quantity = 3
        quick_scan = self._quick_scan(mode="stock", qty=4)
        quick_scan.action_confirm()
        move = quick_scan.line_ids.move_id
        self.assertEqual(move.state, "done")
        self.assertTrue(move.is_inventory)
        self.assertEqual(self._qty(), 9)
        self.assertEqual(quant.inventory_quantity, 3)

    def test_undo(self):
        self.Quant._update_available_quantity(self.product, self.location, 4)
        quick_scan = self._quick_scan(qty=2)
        quick_scan.action_confirm()
        quick_scan.write({"mode": "stock", "product_id": self.product.id, "qty": 3})
        quick_scan.action_confirm()
        self.assertEqual(self._qty(), 5)
        added = quick_scan.line_ids.filtered(lambda line: line.state == "added")
        scrapped = quick_scan.line_ids - added
        added.action_undo()
        self.assertEqual(added.state, "undone")
        self.assertEqual(added.on_hand_after, 2)
        scrapped.action_undo()
        self.assertEqual(scrapped.on_hand_after, 4)
        self.assertEqual(self._qty(), 4)
        with self.assertRaises(UserError):
            scrapped.action_undo()

    def test_refusals(self):
        tracked = self.env["product.product"].create(
            {"name": "Quick Lot", "is_storable": True, "tracking": "lot"}
        )
        self.env["product.product"].create(
            {"name": "Quick Service", "type": "service", "barcode": "NOPE"}
        )
        consumable = self.env["product.product"].create({"name": "Quick Consu"})
        for product, mode in (
            (tracked, "scrap"),
            (tracked, "stock"),
            (consumable, "stock"),
        ):
            with self.assertRaises(UserError):
                self._quick_scan(product_id=product.id, mode=mode).action_confirm()
        with self.assertRaises(UserError):
            self._quick_scan(product_id=False).action_confirm()
        with Form(self.QuickScan) as form:
            form._barcode_scanned = "NOPE"
            self.assertFalse(form.product_id)
