# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import HttpCase, tagged

SCRIPT = """
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitFor(check, what) {
    for (let i = 0; i < 100; i++) {
        if (check()) {
            return;
        }
        await sleep(100);
    }
    throw new Error("Not found: " + what);
}
function scan(barcode) {
    odoo.__WOWL_DEBUG__.root.env.services.barcode.bus.trigger(
        "barcode_scanned", {barcode, target: document.body}
    );
}
const rows = () => document.querySelectorAll(".o_stock_quick_scan tbody tr").length;
(async () => {
    try {
        await waitFor(
            () => document.querySelector(".o_stock_quick_scan select option"),
            "screen"
        );
        scan("QUICKSCAN1");
        scan("QUICKSCAN1");
        await waitFor(() => rows() === 2, "two scrapped");
        const modes = document.querySelectorAll(".o_stock_quick_scan .btn-group .btn");
        modes[1].click();
        scan("QUICKSCAN1");
        await waitFor(() => rows() === 3, "added to stock");
        console.log("test successful");
    } catch (e) {
        console.error(e.message);
    }
})();
"""


@tagged("post_install", "-at_install")
class TestQuickScanUi(HttpCase):
    def test_quick_scan_screen(self):
        product = self.env["product.product"].create(
            {"name": "Quick Scan UI", "is_storable": True, "barcode": "QUICKSCAN1"}
        )
        location = (
            self.env["stock.warehouse"]
            .search([("company_id", "=", self.env.company.id)], limit=1)
            .lot_stock_id
        )
        self.env["stock.quant"]._update_available_quantity(product, location, 5)
        action = self.env.ref("stock_quick_scan.action_quick_scan")
        self.browser_js(f"/odoo/action-{action.id}", SCRIPT, login="admin")
        scraps = self.env["stock.scrap"].search([("product_id", "=", product.id)])
        self.assertEqual(scraps.mapped("state"), ["done", "done"])
        self.assertEqual(product.with_context(location=location.id).qty_available, 4)
