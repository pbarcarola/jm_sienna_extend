# © 2016 Serpent Consulting Services Pvt. Ltd. (http://www.serpentcs.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Sienna Website Extensions",
    "category": "e-commerce",
    "author": "Jose Marty "
    "Jose Marty "
    "Jose Marty",
    "website": "https://martydev.com",
    "version": "16.0.1.0.1",
    "license": "AGPL-3",
    "depends": ["mass_mailing", "website","product_brand", "website_sale","website_sale_product_brand"],
    "data": [
        #"security/ir.model.access.csv",
        #"data/website_menu.xml",
        "views/website.xml",
        "views/website_config.xml",
        "views/product_brand_views.xml",
    ],
    "demo": [
        #"demo/product_brand_demo.xml",
        #"demo/product_product_demo.xml",
    ],
    "assets": {        
    },
    "installable": True,
}
