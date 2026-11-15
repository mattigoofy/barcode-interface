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
const value = (name) =>
    document.querySelector(`.o_field_widget[name='${name}'] input`)?.value
    ?? document.querySelector(`.o_field_widget[name='${name}']`)?.textContent.trim();
const rows = () => document.querySelectorAll(".o_field_widget[name='line_ids'] .o_data_row").length;
const ok = () => document.querySelector("button[name='action_confirm']");
(async () => {
    try {
        await waitFor(() => document.querySelector(".o_form_view"), "form");
        scan("QUICKSCAN1");
        await waitFor(() => ok(), "product shown");
        scan("QUICKSCAN1");
        await waitFor(() => value("qty") === "2.00", "quantity 2");
        await waitFor(() => value("on_hand_after") === "3.00", "stock after");
        ok().click();
        await waitFor(() => rows() === 1 && !ok(), "scrapped two");
        document.querySelector(".o_data_row button[name='action_undo']").click();
        await waitFor(
            () => document.querySelector(".o_data_row .o_field_badge")?.textContent.includes("Undone"),
            "undone"
        );
        console.log("test successful");
    } catch (e) {
        console.error(e.message);
    }
})();
"""


@tagged("post_install", "-at_install")
class TestQuickScanUi(HttpCase):
    def test_quick_scan_form(self):
        product = self.env["product.product"].create(
            {"name": "Quick Scan UI", "is_storable": True, "barcode": "QUICKSCAN1"}
        )
        location = (
            self.env["stock.warehouse"]
            .search([("company_id", "=", self.env.company.id)], limit=1)
            .lot_stock_id
        )
        self.env["stock.quant"]._update_available_quantity(product, location, 5)
        action = self.env.ref("stock_quick_scan.stock_scrap_quick_scan_action")
        self.browser_js(f"/odoo/action-{action.id}", SCRIPT, login="admin")
        self.assertEqual(product.with_context(location=location.id).qty_available, 5)
        line = self.env["stock.scrap.quick.scan.line"].search(
            [("product_id", "=", product.id)]
        )
        self.assertEqual(line.state, "undone")
        self.assertEqual(line.qty, 2)
