# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, api, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_compare


class StockScrap(models.Model):
    _inherit = "stock.scrap"

    # --- helpers ---------------------------------------------------------------

    @api.model
    def _quick_scan_check_access(self):
        if not self.env.user.has_group("stock.group_stock_user"):
            raise AccessError(self.env._("Only inventory users can use Quick Scan."))

    @api.model
    def _quick_scan_location(self, location_id):
        location = self.env["stock.location"].browse(location_id).exists()
        if not location or location.usage != "internal":
            raise UserError(self.env._("The selected location is no longer valid."))
        return location

    @api.model
    def _quick_scan_product(self, product_id, storable=False):
        product = self.env["product.product"].browse(product_id).exists()
        if not product:
            raise UserError(self.env._("The scanned product no longer exists."))
        if product.type != "consu" or (storable and not product.is_storable):
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
        return product

    @api.model
    def _quick_scan_qty(self, product, qty):
        qty = float(qty or 0)
        if float_compare(qty, 0, precision_rounding=product.uom_id.rounding) <= 0:
            raise UserError(self.env._("The quantity must be positive."))
        return qty

    # --- actions called by the Quick Scan screen -----------------------------

    @api.model
    def action_quick_scan_data(self):
        """What the Quick Scan screen offers: the internal locations (and the
        main warehouse's stock as default), the scrap locations (and the one a
        new scrap gets by default), and the scrap reasons."""
        self._quick_scan_check_access()
        company = self.env.company
        Location = self.env["stock.location"]
        company_domain = Location._check_company_domain(company)
        locations = Location.search([("usage", "=", "internal")] + company_domain)
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        )
        scrap_locations = Location.search(
            [("scrap_location", "=", True)] + company_domain
        )
        default_scrap = self.new({"company_id": company.id}).scrap_location_id
        reasons = self.env["stock.scrap.reason.tag"].search([])
        return {
            "locations": [
                {"id": loc.id, "name": loc.display_name} for loc in locations
            ],
            "location_id": warehouse.lot_stock_id.id or locations[:1].id or False,
            "scrap_locations": [
                {"id": loc.id, "name": loc.display_name} for loc in scrap_locations
            ],
            "scrap_location_id": (default_scrap & scrap_locations).id
            or scrap_locations[:1].id
            or False,
            "reasons": [{"id": r.id, "name": r.name} for r in reasons],
        }

    @api.model
    def action_quick_scan_scrap(
        self,
        location_id,
        product_id,
        qty=1.0,
        reason_tag_ids=None,
        scrap_location_id=False,
        force=False,
    ):
        """Scrap ``qty`` of a product from a location and validate it at once.

        When the location holds less than that, nothing is done unless
        ``force`` is set: the available quantity is returned so the screen can
        ask, as the back office's insufficient-quantity wizard does.
        """
        self._quick_scan_check_access()
        location = self._quick_scan_location(location_id)
        product = self._quick_scan_product(product_id)
        qty = self._quick_scan_qty(product, qty)
        vals = {
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "scrap_qty": qty,
            "location_id": location.id,
            "company_id": (location.company_id or self.env.company).id,
            "scrap_reason_tag_ids": [Command.set(reason_tag_ids or [])],
        }
        if scrap_location_id:
            vals["scrap_location_id"] = scrap_location_id
        if not force and not self.new(vals).check_available_qty():
            available = product.with_context(
                location=location.id, package_id=False, owner_id=False, strict=True
            ).qty_available
            return {"done": False, "available": available, "uom": product.uom_id.name}
        scrap = self.create(vals)
        if force and not scrap.check_available_qty():
            scrap.do_scrap()
        elif isinstance(scrap.action_validate(), dict):
            raise UserError(
                self.env._(
                    "The stock of %(name)s changed while scrapping. Please try again.",
                    name=product.display_name,
                )
            )
        return {"done": True, "name": scrap.name}

    @api.model
    def action_quick_scan_add_stock(self, location_id, product_id, qty=1.0):
        """Put ``qty`` of a product in stock at a location at once.

        It books the same validated move an applied inventory adjustment does
        (inventory loss location -> location), without touching a count that
        may be in progress on the quant.
        """
        self._quick_scan_check_access()
        location = self._quick_scan_location(location_id)
        product = self._quick_scan_product(product_id, storable=True)
        qty = self._quick_scan_qty(product, qty)
        company = location.company_id or self.env.company
        quant = self.env["stock.quant"].new(
            {"product_id": product.id, "location_id": location.id}
        )
        move_vals = quant.with_context(
            inventory_name=self.env._("Quick Scan")
        )._get_inventory_move_values(
            qty, product.with_company(company).property_stock_inventory, location
        )
        move = (
            self.env["stock.move"].with_context(inventory_mode=False).create(move_vals)
        )
        move._action_done()
        return {"done": True, "move_id": move.id}
