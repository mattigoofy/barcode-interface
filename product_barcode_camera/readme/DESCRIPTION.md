Adds a camera button, to scan a barcode instead of typing it:

- on every field that points to a product (sales and purchase lines, scrap,
  stock moves, inventory, ...), not only where a view enables it with
  `can_scan_barcode`: scan, and the product is filled in;
- on the **Barcode** field of a product (product and variant forms): scan the
  label, and its barcode is filled in.

Same conditions as Odoo's own camera buttons: on a phone or tablet, with the
camera available (HTTPS or localhost).
