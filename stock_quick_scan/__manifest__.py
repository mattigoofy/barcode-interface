{
    "name": "Stock Quick Scan",
    "version": "18.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Scan a product to scrap it or put it in stock at once",
    "author": "Mathias",
    "website": "https://github.com/synvio-mgo/barcode-interface",
    "license": "AGPL-3",
    "depends": [
        "barcodes",
        "stock",
    ],
    "data": [
        "views/quick_scan_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_quick_scan/static/src/quick_scan/*",
            "stock_quick_scan/static/src/product_barcode/*",
        ],
    },
    "installable": True,
    "auto_install": False,
}
