{
    "name": "Product Barcode Camera",
    "version": "18.0.1.0.0",
    "category": "Hidden/Tools",
    "summary": "Camera button to scan a barcode on every product field",
    "author": "Mathias",
    "website": "https://github.com/synvio-mgo/barcode-interface",
    "license": "AGPL-3",
    "depends": [
        "product",
    ],
    "assets": {
        "web.assets_backend": [
            "product_barcode_camera/static/src/many2one_field_patch.js",
        ],
    },
    "installable": True,
    "auto_install": False,
}
