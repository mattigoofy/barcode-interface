{
    "name": "Stock Quick Scan",
    "version": "18.0.1.2.0",
    "category": "Inventory/Inventory",
    "summary": "Scan a product to scrap it or put it in stock",
    "author": "Mathias",
    "website": "https://github.com/synvio-mgo/barcode-interface",
    "license": "AGPL-3",
    "depends": [
        "barcodes",
        "stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/quick_scan_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
