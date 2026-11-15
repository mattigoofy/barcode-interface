# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, fields, models
from odoo.exceptions import UserError


class StockScrapQuickScanLine(models.TransientModel):
    _name = "stock.scrap.quick.scan.line"
    _description = "Quick Scan Line"
    _order = "id desc"

    quick_scan_id = fields.Many2one(
        "stock.scrap.quick.scan", required=True, ondelete="cascade"
    )
    product_id = fields.Many2one("product.product", string="Product", required=True)
    product_image = fields.Image(related="product_id.image_128")
    qty = fields.Float(string="Quantity", digits="Product Unit of Measure")
    uom_id = fields.Many2one(related="product_id.uom_id")
    on_hand_after = fields.Float(
        string="In Stock After", digits="Product Unit of Measure"
    )
    move_id = fields.Many2one("stock.move", required=True)
    state = fields.Selection(
        [("scrapped", "Scrapped"), ("added", "Added"), ("undone", "Undone")],
        required=True,
    )

    def action_undo(self):
        for line in self:
            move = line.move_id
            if line.state == "undone" or move.returned_move_ids:
                raise UserError(self.env._("This scan has already been undone."))
            if move.state != "done":
                raise UserError(self.env._("This scan can no longer be undone."))
            line_vals = {
                "product_id": move.product_id.id,
                "product_uom_id": move.product_uom.id,
                "quantity": move.quantity,
                "location_id": move.location_dest_id.id,
                "location_dest_id": move.location_id.id,
                "company_id": move.company_id.id,
            }
            reverse = (
                self.env["stock.move"]
                .with_context(inventory_mode=False)
                .create(
                    {
                        "name": self.env._(
                            "Quick Scan undo: %(ref)s", ref=move.reference
                        ),
                        "origin": move.reference,
                        "product_id": move.product_id.id,
                        "product_uom": move.product_uom.id,
                        "product_uom_qty": move.quantity,
                        "company_id": move.company_id.id,
                        "location_id": move.location_dest_id.id,
                        "location_dest_id": move.location_id.id,
                        "is_inventory": move.is_inventory,
                        "origin_returned_move_id": move.id,
                        "state": "confirmed",
                        "picked": True,
                        "move_line_ids": [Command.create(line_vals)],
                    }
                )
            )
            reverse._action_done()
            internal = move.location_id if move.scrap_id else move.location_dest_id
            move.product_id.invalidate_recordset(["qty_available"])
            line.write(
                {
                    "state": "undone",
                    "on_hand_after": move.product_id.with_context(
                        location=internal.id
                    ).qty_available,
                }
            )
        return True
