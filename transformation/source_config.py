"""Explicit source scope; unknown sources never fall through to another channel."""
SOURCES = {
    'internal_web': ('WEB01', '', 'website_orders', 'website_workflow'),
    'ebay_sim': ('seller_sim_01', 'ebay_', 'ebay_orders', 'ebay_workflow'),
    'etsy_sim': ('7001', 'etsy_', 'etsy_orders', 'etsy_workflow'),
}
