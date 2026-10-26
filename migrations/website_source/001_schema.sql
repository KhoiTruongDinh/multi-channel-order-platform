\set ON_ERROR_STOP on
BEGIN;

SET ROLE website_owner;

CREATE TABLE IF NOT EXISTS public.customers (
    customer_id TEXT PRIMARY KEY CHECK (btrim(customer_id) <> ''),
    display_name TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS public.products (
    product_id TEXT PRIMARY KEY CHECK (btrim(product_id) <> ''),
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS public.product_variants (
    variant_id TEXT PRIMARY KEY CHECK (btrim(variant_id) <> ''),
    product_id TEXT NOT NULL REFERENCES public.products(product_id),
    sku TEXT NOT NULL UNIQUE CHECK (btrim(sku) <> ''),
    attributes JSONB NOT NULL CHECK (jsonb_typeof(attributes) = 'object'),
    current_price NUMERIC(18,2) NOT NULL CHECK (current_price >= 0),
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    is_active BOOLEAN NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS public.orders (
    order_id TEXT PRIMARY KEY CHECK (btrim(order_id) <> ''),
    order_number TEXT NOT NULL UNIQUE CHECK (btrim(order_number) <> ''),
    customer_id TEXT NOT NULL REFERENCES public.customers(customer_id),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL CHECK (updated_at >= created_at),
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    payment_status TEXT NOT NULL CHECK (payment_status IN ('UNPAID', 'PAID')),
    fulfillment_status TEXT NOT NULL CHECK (fulfillment_status IN ('NOT_STARTED', 'PARTIALLY_SHIPPED', 'SHIPPED', 'DELIVERED')),
    cancellation_status TEXT NOT NULL CHECK (cancellation_status IN ('NOT_REQUESTED', 'REQUESTED', 'CANCELED')),
    items_gross_amount NUMERIC(18,2) NOT NULL CHECK (items_gross_amount >= 0),
    discount_amount NUMERIC(18,2) NOT NULL CHECK (discount_amount >= 0),
    shipping_amount NUMERIC(18,2) NOT NULL CHECK (shipping_amount >= 0),
    tax_amount NUMERIC(18,2) NOT NULL CHECK (tax_amount >= 0),
    order_total_amount NUMERIC(18,2) NOT NULL CHECK (order_total_amount >= 0),
    CHECK (order_total_amount = items_gross_amount - discount_amount + shipping_amount + tax_amount)
);

CREATE INDEX IF NOT EXISTS orders_updated_at_idx ON public.orders(updated_at, order_id);

CREATE TABLE IF NOT EXISTS public.order_items (
    order_item_id TEXT PRIMARY KEY CHECK (btrim(order_item_id) <> ''),
    order_id TEXT NOT NULL REFERENCES public.orders(order_id),
    variant_id TEXT NOT NULL REFERENCES public.product_variants(variant_id),
    sku_at_purchase TEXT NOT NULL,
    title_at_purchase TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(18,2) NOT NULL CHECK (unit_price >= 0),
    line_discount_amount NUMERIC(18,2) NOT NULL CHECK (line_discount_amount >= 0 AND line_discount_amount <= quantity * unit_price),
    line_tax_amount NUMERIC(18,2) NOT NULL CHECK (line_tax_amount >= 0),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS public.payment_transactions (
    payment_transaction_id TEXT PRIMARY KEY CHECK (btrim(payment_transaction_id) <> ''),
    order_id TEXT NOT NULL REFERENCES public.orders(order_id),
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('PAYMENT', 'REFUND')),
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'SUCCEEDED', 'FAILED')),
    amount NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    provider_reference TEXT,
    occurred_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS public.shipments (
    shipment_id TEXT PRIMARY KEY CHECK (btrim(shipment_id) <> ''),
    order_id TEXT NOT NULL REFERENCES public.orders(order_id),
    carrier TEXT,
    tracking_number TEXT,
    status TEXT NOT NULL CHECK (status IN ('SHIPPED', 'DELIVERED')),
    shipped_at TIMESTAMPTZ NOT NULL,
    delivered_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (delivered_at IS NULL OR delivered_at >= shipped_at),
    CHECK ((status = 'DELIVERED') = (delivered_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS public.shipment_items (
    shipment_id TEXT NOT NULL REFERENCES public.shipments(shipment_id),
    order_item_id TEXT NOT NULL REFERENCES public.order_items(order_item_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (shipment_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS public.cancellation_requests (
    cancellation_id TEXT PRIMARY KEY CHECK (btrim(cancellation_id) <> ''),
    order_id TEXT NOT NULL REFERENCES public.orders(order_id),
    reason_code TEXT NOT NULL CHECK (reason_code IN ('CUSTOMER_REQUEST')),
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    requested_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK ((status = 'PENDING') = (resolved_at IS NULL)),
    CHECK (resolved_at IS NULL OR resolved_at >= requested_at)
);

REVOKE ALL ON public.customers, public.products, public.product_variants,
    public.orders, public.order_items, public.payment_transactions,
    public.shipments, public.shipment_items, public.cancellation_requests
    FROM PUBLIC;
GRANT SELECT ON public.customers, public.products, public.product_variants,
    public.orders, public.order_items, public.payment_transactions,
    public.shipments, public.shipment_items, public.cancellation_requests
    TO website_reader;

RESET ROLE;
INSERT INTO public.schema_migrations (migration_name)
VALUES ('website_source/001_schema.sql') ON CONFLICT DO NOTHING;
COMMIT;
