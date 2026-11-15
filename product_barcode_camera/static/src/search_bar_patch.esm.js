import {Domain} from "@web/core/domain";
import {SearchBar} from "@web/search/search_bar/search_bar";
import {_t} from "@web/core/l10n/translation";
import {isBarcodeScannerSupported} from "@web/core/barcode/barcode_video_scanner";
import {isMobileOS} from "@web/core/browser/feature_detection";
import {patch} from "@web/core/utils/patch";
import {scanBarcode} from "@web/core/barcode/barcode_dialog";

const PRODUCT_MODELS = ["product.product", "product.template"];

/**
 * A camera button in the search bar of the product lists, to find a product by
 * scanning its label. The scanned code becomes a filter on the barcode or the
 * internal reference. Same conditions as the other camera buttons.
 */
patch(SearchBar.prototype, {
    get hasProductBarcodeCamera() {
        return (
            PRODUCT_MODELS.includes(this.env.searchModel.resModel) &&
            isMobileOS() &&
            isBarcodeScannerSupported()
        );
    },

    async onProductBarcodeCameraClick() {
        const barcode = await scanBarcode(this.env);
        if (!barcode) {
            return;
        }
        const domain = new Domain([
            "|",
            ["barcode", "=", barcode],
            ["default_code", "=", barcode],
        ]);
        this.env.searchModel.createNewFilters([
            {
                description: _t("Barcode: %(barcode)s", {barcode}),
                domain: domain.toString(),
            },
        ]);
    },
});
