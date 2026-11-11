import {Component, onWillStart, useState} from "@odoo/owl";
import {BarcodeDialog} from "@web/core/barcode/barcode_dialog";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {Layout} from "@web/search/layout";
import {_t} from "@web/core/l10n/translation";
import {browser} from "@web/core/browser/browser";
import {formatFloat} from "@web/core/utils/numbers";
import {isBarcodeScannerSupported} from "@web/core/barcode/barcode_video_scanner";
import {registry} from "@web/core/registry";
import {standardActionServiceProps} from "@web/webclient/actions/action_service";
import {useBus, useService} from "@web/core/utils/hooks";

const STORAGE_KEY = "stock_quick_scan";
const LOG_LIMIT = 30;

function loadPrefs() {
    try {
        return JSON.parse(browser.localStorage.getItem(STORAGE_KEY)) || {};
    } catch {
        return {};
    }
}

function savePrefs(prefs) {
    try {
        browser.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch {
        // Only a convenience: the screen works without it.
    }
}

/**
 * Quick Scan: every product scanned is scrapped, or put in stock, at once.
 *
 * A plain Odoo screen under Inventory. A scan comes from a hardware scanner
 * (Odoo's barcode service), the barcode field, or the phone camera (Odoo's own
 * scanner dialog). Scans are handled one after the other, so scanning fast is
 * never refused.
 */
export class QuickScan extends Component {
    static template = "stock_quick_scan.QuickScan";
    static components = {Layout};
    static props = {...standardActionServiceProps};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        const prefs = loadPrefs();
        this.state = useState({
            mode: prefs.mode === "stock" ? "stock" : "scrap",
            locations: [],
            locationId: null,
            scrapLocations: [],
            scrapLocationId: null,
            reasons: [],
            reasonIds: [],
            code: "",
            log: [],
            pending: 0,
        });
        this.display = {controlPanel: {}};
        this.cameraSupported = isBarcodeScannerSupported();
        this._queue = Promise.resolve();
        this._logSeq = 0;

        useBus(useService("barcode").bus, "barcode_scanned", (ev) => {
            // Typed into the barcode field: its own Enter handles it.
            if (ev.detail.target?.closest?.(".o_stock_quick_scan_input")) {
                return;
            }
            this.scan(ev.detail.barcode);
        });

        onWillStart(async () => {
            const data = await this.orm.call("stock.scrap", "action_quick_scan_data");
            this.state.locations = data.locations;
            this.state.scrapLocations = data.scrap_locations;
            this.state.reasons = data.reasons;
            const known = (list, id) => list.some((item) => item.id === id);
            this.state.locationId = known(data.locations, prefs.locationId)
                ? prefs.locationId
                : data.location_id;
            this.state.scrapLocationId = known(
                data.scrap_locations,
                prefs.scrapLocationId
            )
                ? prefs.scrapLocationId
                : data.scrap_location_id;
            this.state.reasonIds = (prefs.reasonIds || []).filter((id) =>
                known(data.reasons, id)
            );
        });
    }

    // --- settings -------------------------------------------------------------

    remember() {
        savePrefs({
            mode: this.state.mode,
            locationId: this.state.locationId,
            scrapLocationId: this.state.scrapLocationId,
            reasonIds: this.state.reasonIds,
        });
    }

    setMode(mode) {
        this.state.mode = mode;
        this.remember();
    }

    setLocation(value) {
        this.state.locationId = parseInt(value, 10) || null;
        this.remember();
    }

    setScrapLocation(value) {
        this.state.scrapLocationId = parseInt(value, 10) || null;
        this.remember();
    }

    toggleReason(reason) {
        const index = this.state.reasonIds.indexOf(reason.id);
        if (index === -1) {
            this.state.reasonIds.push(reason.id);
        } else {
            this.state.reasonIds.splice(index, 1);
        }
        this.remember();
    }

    // --- scanning -------------------------------------------------------------

    onCodeKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            const code = this.state.code.trim();
            this.state.code = "";
            if (code) {
                this.scan(code);
            }
        }
    }

    /**
     * Open Odoo's scanner dialog on the back camera. Settles with the code
     * read, or with null once the dialog is closed without one.
     */
    onCameraClick() {
        new Promise((resolve) => {
            this.dialog.add(
                BarcodeDialog,
                {facingMode: "environment", onResult: resolve, onError: () => undefined},
                {onClose: () => Promise.resolve().then(() => resolve(null))}
            );
        }).then((code) => code && this.scan(code));
    }

    scan(code) {
        // Queue the scan behind the ones still running instead of refusing it.
        this.state.pending++;
        this._queue = this._queue
            .then(() => this.process(code))
            .catch(() => undefined)
            .finally(() => this.state.pending--);
        return this._queue;
    }

    async process(code) {
        const products = await this.orm.searchRead(
            "product.product",
            [
                ["type", "=", "consu"],
                "|",
                ["barcode", "=", code],
                ["default_code", "=", code],
            ],
            ["display_name", "uom_id"],
            {limit: 1}
        );
        if (!products.length) {
            this.notification.add(_t("No product matches “%(code)s”.", {code}), {
                type: "warning",
            });
            return;
        }
        const product = products[0];
        const done =
            this.state.mode === "stock"
                ? await this.addToStock(product)
                : await this.scrap(product);
        if (done) {
            this.state.log.unshift({
                id: ++this._logSeq,
                mode: this.state.mode,
                name: product.display_name,
                qty: "1",
                uom: product.uom_id[1],
                time: new Date().toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                }),
            });
            this.state.log.splice(LOG_LIMIT);
        }
    }

    async scrap(product, force = false) {
        const result = await this.orm.call(
            "stock.scrap",
            "action_quick_scan_scrap",
            [this.state.locationId, product.id, 1],
            {
                reason_tag_ids: this.state.reasonIds,
                scrap_location_id: this.state.scrapLocationId,
                force,
            }
        );
        if (result.done) {
            this.notification.add(
                _t("Scrapped 1 %(uom)s of %(name)s.", {
                    uom: product.uom_id[1],
                    name: product.display_name,
                }),
                {type: "success"}
            );
            return true;
        }
        const confirmed = await new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Not enough stock"),
                body: _t(
                    "%(name)s: %(available)s %(uom)s in this location. Scrap anyway?",
                    {
                        name: product.display_name,
                        available: formatFloat(result.available, {trailingZeros: false}),
                        uom: result.uom,
                    }
                ),
                confirmLabel: _t("Scrap anyway"),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
                dismiss: () => resolve(false),
            });
        });
        return confirmed ? this.scrap(product, true) : false;
    }

    async addToStock(product) {
        await this.orm.call("stock.scrap", "action_quick_scan_add_stock", [
            this.state.locationId,
            product.id,
            1,
        ]);
        this.notification.add(
            _t("Added 1 %(uom)s of %(name)s to stock.", {
                uom: product.uom_id[1],
                name: product.display_name,
            }),
            {type: "success"}
        );
        return true;
    }
}

registry.category("actions").add("stock_quick_scan", QuickScan);
