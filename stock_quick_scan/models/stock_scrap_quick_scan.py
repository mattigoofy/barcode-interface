# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare

QUICK_SCAN_MODES = [("scrap", "Scrap"), ("stock", "Add to Stock")]


class StockScrapQuickScan(models.TransientModel):
    _name = "stock.scrap.quick.scan"
    _inherit = ["barcodes.barcode_events_mixin"]
    _description = "Quick Scan"

    mode = fields.Selection(QUICK_SCAN_MODES, required=True, default="scrap")
    location_id = fields.Many2one(
        "stock.location",
        string="Location",
        required=True,
        domain="[('usage', '=', 'internal')]",
    )
    scrap_location_id = fields.Many2one(
        "stock.location",
        string="Scrap Location",
        domain="[('scrap_location', '=', True)]",
    )
    scrap_reason_tag_ids = fields.Many2many(
        "stock.scrap.reason.tag", string="Reasons"
    )
    product_id = fields.Many2one(
        "product.product", string="Product", domain="[('type', '=', 'consu')]"
    )
    product_image = fields.Image(related="product_id.image_256")
    uom_id = fields.Many2one(related="product_id.uom_id")
    qty = fields.Float(
        string="Quantity", digits="Product Unit of Measure", default=1.0
    )
    on_hand = fields.Float(
        string="In Stock",
        digits="Product Unit of Measure",
        compute="_compute_on_hand",
    )
    on_hand_after = fields.Float(
        string="In Stock After",
        digits="Product Unit of Measure",
        compute="_compute_on_hand_after",
    )
    line_ids = fields.One2many("stock.scrap.quick.scan.line", "quick_scan_id")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        last = self.search([("create_uid", "=", self.env.uid)], order="id desc", limit=1)
        if last:
            res.update(
                {
                    "mode": last.mode,
                    "location_id": last.location_id.id,
                    "scrap_location_id": last.scrap_location_id.id,
                    "scrap_reason_tag_ids": [
                        Command.set(last.scrap_reason_tag_ids.ids)
                    ],
                }
            )
        else:
            company = self.env.company
            warehouse = self.env["stock.warehouse"].search(
                [("company_id", "=", company.id)], limit=1
            )
            res.update(
                {
                    "location_id": warehouse.lot_stock_id.id,
                    "scrap_location_id": self.env["stock.scrap"]
                    .new({"company_id": company.id})
                    .scrap_location_id.id,
                }
            )
        return {key: value for key, value in res.items() if key in fields_list}

    @api.depends("product_id", "location_id")
    def _compute_on_hand(self):
        for quick_scan in self:
            quick_scan.on_hand = (
                quick_scan.product_id.with_context(
                    location=quick_scan.location_id.id
                ).qty_available
                if quick_scan.product_id and quick_scan.location_id
                else 0.0
            )

    @api.depends("on_hand", "qty", "mode")
    def _compute_on_hand_after(self):
        for quick_scan in self:
            sign = 1 if quick_scan.mode == "stock" else -1
            quick_scan.on_hand_after = quick_scan.on_hand + sign * quick_scan.qty

    @api.onchange("product_id")
    def _onchange_product_id(self):
        self.qty = 1.0

    def on_barcode_scanned(self, barcode):
        product = self.env["product.product"].search(
            [
                ("type", "=", "consu"),
                "|",
                ("barcode", "=", barcode),
                ("default_code", "=", barcode),
            ],
            limit=1,
        )
        if not product:
            return {
                "warning": {
                    "title": self.env._("Unknown barcode"),
                    "message": self.env._(
                        "No product matches “%(code)s”.", code=barcode
                    ),
                }
            }
        if product == self.product_id:
            self.qty += 1
        else:
            self.product_id = product
            self.qty = 1.0

    def _check_product(self):
        product = self.product_id
        if not product:
            raise UserError(self.env._("Scan or pick a product first."))
        if self.mode == "stock" and not product.is_storable:
            raise UserError(
                self.env._(
                    "%(name)s does not track inventory.", name=product.display_name
                )
            )
        if product.tracking != "none":
            raise UserError(
                self.env._(
                    "%(name)s is tracked by lot/serial number: use the regular "
                    "Scrap or Physical Inventory screen for it.",
                    name=product.display_name,
                )
            )
        if float_compare(self.qty, 0, precision_rounding=product.uom_id.rounding) <= 0:
            raise UserError(self.env._("The quantity must be positive."))

    def _scrap(self):
        if not self.scrap_location_id:
            raise UserError(self.env._("Choose a scrap location first."))
        scrap = self.env["stock.scrap"].create(
            {
                "product_id": self.product_id.id,
                "product_uom_id": self.product_id.uom_id.id,
                "scrap_qty": self.qty,
                "location_id": self.location_id.id,
                "scrap_location_id": self.scrap_location_id.id,
                "company_id": (self.location_id.company_id or self.env.company).id,
                "scrap_reason_tag_ids": [Command.set(self.scrap_reason_tag_ids.ids)],
            }
        )
        # The stock was shown before OK: scrapping more than that is a choice,
        # so skip the insufficient-quantity wizard of action_validate.
        scrap.do_scrap()
        return scrap.move_ids[:1]

    def _add_to_stock(self):
        company = self.location_id.company_id or self.env.company
        quant = self.env["stock.quant"].new(
            {"product_id": self.product_id.id, "location_id": self.location_id.id}
        )
        move_vals = quant.with_context(
            inventory_name=self.env._("Quick Scan")
        )._get_inventory_move_values(
            self.qty,
            self.product_id.with_company(company).property_stock_inventory,
            self.location_id,
        )
        move = (
            self.env["stock.move"].with_context(inventory_mode=False).create(move_vals)
        )
        move._action_done()
        return move

    def action_confirm(self):
        self.ensure_one()
        self._check_product()
        move = self._scrap() if self.mode == "scrap" else self._add_to_stock()
        self.product_id.invalidate_recordset(["qty_available"])
        self.env["stock.scrap.quick.scan.line"].create(
            {
                "quick_scan_id": self.id,
                "product_id": self.product_id.id,
                "qty": self.qty,
                "move_id": move.id,
                "state": "scrapped" if self.mode == "scrap" else "added",
                "on_hand_after": self.product_id.with_context(
                    location=self.location_id.id
                ).qty_available,
            }
        )
        self.write({"product_id": False, "qty": 1.0})
        return True

    def action_clear(self):
        self.write({"product_id": False, "qty": 1.0})
        return True
