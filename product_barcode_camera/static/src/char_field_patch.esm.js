import {CharField} from "@web/views/fields/char/char_field";
import {isBarcodeScannerSupported} from "@web/core/barcode/barcode_video_scanner";
import {isMobileOS} from "@web/core/browser/feature_detection";
import {patch} from "@web/core/utils/patch";
import {scanBarcode} from "@web/core/barcode/barcode_dialog";

const PRODUCT_MODELS = ["product.product", "product.template"];

/**
 * A camera button on the Barcode field of a product, to fill it in by scanning
 * the label instead of typing it. Same conditions as Odoo's other camera
 * buttons: phone or tablet, camera available (HTTPS or localhost).
 */
patch(CharField.prototype, {
    get hasProductBarcodeCamera() {
        return (
            this.props.name === "barcode" &&
            PRODUCT_MODELS.includes(this.props.record.resModel) &&
            isMobileOS() &&
            isBarcodeScannerSupported()
        );
    },

    async onProductBarcodeCameraClick() {
        const barcode = await scanBarcode(this.env);
        if (barcode) {
            await this.props.record.update({[this.props.name]: barcode});
        }
    },
});
