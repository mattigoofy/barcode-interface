# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestQuickScan(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Scrap = cls.env["stock.scrap"]
        cls.Quant = cls.env["stock.quant"]
        cls.location = cls.env["stock.location"].create(
            {
                "name": "Quick Scan Shelf",
                "usage": "internal",
                "location_id": cls.env.ref("stock.stock_location_stock").id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Quick Untracked", "is_storable": True}
        )
        cls.reason = cls.env["stock.scrap.reason.tag"].create({"name": "Broken"})

    def _qty(self):
        return self.product.with_context(location=self.location.id).qty_available

    def test_data(self):
        data = self.Scrap.action_quick_scan_data()
        self.assertIn(self.location.id, [loc["id"] for loc in data["locations"]])
        self.assertTrue(data["location_id"])
        self.assertTrue(data["scrap_location_id"])
        self.assertIn(self.reason.id, [r["id"] for r in data["reasons"]])

    def test_scrap(self):
        self.Quant._update_available_quantity(self.product, self.location, 3)
        res = self.Scrap.action_quick_scan_scrap(
            self.location.id, self.product.id, 1, reason_tag_ids=[self.reason.id]
        )
        self.assertTrue(res["done"])
        scrap = self.Scrap.search([("name", "=", res["name"])])
        self.assertEqual(scrap.state, "done")
        self.assertEqual(scrap.scrap_reason_tag_ids, self.reason)
        self.assertEqual(self._qty(), 2)

    def test_scrap_not_enough_asks_first(self):
        res = self.Scrap.action_quick_scan_scrap(self.location.id, self.product.id)
        self.assertFalse(res["done"])
        self.assertEqual(res["available"], 0)
        self.assertFalse(self.Scrap.search([("product_id", "=", self.product.id)]))
        res = self.Scrap.action_quick_scan_scrap(
            self.location.id, self.product.id, force=True
        )
        self.assertTrue(res["done"])
        self.assertEqual(self._qty(), -1)

    def test_add_stock_keeps_a_count_in_progress(self):
        self.Quant._update_available_quantity(self.product, self.location, 5)
        quant = self.Quant._gather(self.product, self.location)
        quant.inventory_quantity = 3
        res = self.Scrap.action_quick_scan_add_stock(self.location.id, self.product.id)
        move = self.env["stock.move"].browse(res["move_id"])
        self.assertEqual(move.state, "done")
        self.assertTrue(move.is_inventory)
        self.assertEqual(self._qty(), 6)
        self.assertEqual(quant.inventory_quantity, 3)

    def test_refusals(self):
        tracked = self.env["product.product"].create(
            {"name": "Quick Lot", "is_storable": True, "tracking": "lot"}
        )
        service = self.env["product.product"].create(
            {"name": "Quick Service", "type": "service"}
        )
        for product in (tracked, service):
            with self.assertRaises(UserError):
                self.Scrap.action_quick_scan_add_stock(self.location.id, product.id)
            with self.assertRaises(UserError):
                self.Scrap.action_quick_scan_scrap(self.location.id, product.id)
