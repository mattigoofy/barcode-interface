import {Many2OneField} from "@web/views/fields/many2one/many2one_field";
import {isBarcodeScannerSupported} from "@web/core/barcode/barcode_video_scanner";
import {isMobileOS} from "@web/core/browser/feature_detection";
import {patch} from "@web/core/utils/patch";

const PRODUCT_MODELS = ["product.product", "product.template"];

/**
 * Odoo's camera button on every product field, not only where a view sets
 * `can_scan_barcode`. Same conditions as Odoo otherwise: phone or tablet,
 * camera available (HTTPS or localhost).
 */
patch(Many2OneField.prototype, {
    get hasBarcodeButton() {
        if (!this.props.canScanBarcode && PRODUCT_MODELS.includes(this.relation)) {
            return (
                isMobileOS() && isBarcodeScannerSupported() && !this.hasExternalButton
            );
        }
        return super.hasBarcodeButton;
    },
});
