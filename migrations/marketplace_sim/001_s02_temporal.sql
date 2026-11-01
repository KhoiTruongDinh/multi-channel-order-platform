\set ON_ERROR_STOP on
BEGIN;
SELECT 'CREATE ROLE s02_ebay_reader LOGIN' WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname='s02_ebay_reader') \gexec
SELECT 'CREATE ROLE s02_etsy_reader LOGIN' WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname='s02_etsy_reader') \gexec
GRANT CONNECT ON DATABASE marketplace_sim TO s02_ebay_reader,s02_etsy_reader;
SET ROLE marketplace_owner;
CREATE SCHEMA IF NOT EXISTS s02 AUTHORIZATION marketplace_owner;
REVOKE ALL ON SCHEMA s02 FROM PUBLIC;
CREATE TABLE IF NOT EXISTS s02.campaigns (
 id TEXT PRIMARY KEY CHECK(id ~ '^[0-9a-f]{12}$'),
 seed INTEGER NOT NULL CHECK(seed>=0), config JSONB NOT NULL CHECK(jsonb_typeof(config)='object'),
 checksum TEXT NOT NULL CHECK(checksum ~ '^[0-9a-f]{64}$'), sealed BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS s02.orders (
 campaign_id TEXT NOT NULL REFERENCES s02.campaigns(id), source TEXT NOT NULL,
 account_id TEXT NOT NULL, order_id TEXT NOT NULL CHECK(btrim(order_id)<>''),
 base JSONB NOT NULL CHECK(jsonb_typeof(base)='object'),
 PRIMARY KEY(campaign_id,source,account_id,order_id),
 CHECK((source='ebay_sim' AND account_id='seller_sim_01') OR (source='etsy_sim' AND account_id='7001'))
);
CREATE TABLE IF NOT EXISTS s02.components (
 campaign_id TEXT NOT NULL, source TEXT NOT NULL, account_id TEXT NOT NULL, order_id TEXT NOT NULL,
 digest TEXT NOT NULL CHECK(digest ~ '^[0-9a-f]{64}$'), body JSONB NOT NULL CHECK(jsonb_typeof(body)='object'),
 PRIMARY KEY(campaign_id,source,account_id,order_id,digest),
 FOREIGN KEY(campaign_id,source,account_id,order_id) REFERENCES s02.orders
);
CREATE TABLE IF NOT EXISTS s02.versions (
 campaign_id TEXT NOT NULL, source TEXT NOT NULL, account_id TEXT NOT NULL, order_id TEXT NOT NULL,
 sequence INTEGER NOT NULL CHECK(sequence>0), visible_at TIMESTAMPTZ NOT NULL,
 source_updated_at TIMESTAMPTZ NOT NULL, header JSONB NOT NULL CHECK(jsonb_typeof(header)='object'),
 component_digest TEXT NOT NULL,
 PRIMARY KEY(campaign_id,source,account_id,order_id,sequence),
 UNIQUE(campaign_id,source,account_id,order_id,visible_at),
 UNIQUE(campaign_id,source,account_id,order_id,source_updated_at),
 FOREIGN KEY(campaign_id,source,account_id,order_id,component_digest) REFERENCES s02.components
);
CREATE INDEX IF NOT EXISTS versions_asof ON s02.versions(campaign_id,source,account_id,order_id,visible_at DESC);
CREATE TABLE IF NOT EXISTS s02.deliveries (
 campaign_id TEXT NOT NULL REFERENCES s02.campaigns(id), message_id TEXT NOT NULL,
 receipt_id TEXT NOT NULL, due_at TIMESTAMPTZ NOT NULL,
 event_type TEXT NOT NULL CHECK(event_type IN ('order.paid','order.shipped')), omitted BOOLEAN NOT NULL,
 attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts>=0), delivered_at TIMESTAMPTZ,
 last_status INTEGER CHECK(last_status BETWEEN 100 AND 599), PRIMARY KEY(campaign_id,message_id)
);
CREATE OR REPLACE FUNCTION s02.immutable_source() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cid TEXT;
BEGIN
 IF TG_TABLE_NAME='campaigns' THEN
  IF TG_OP<>'INSERT' AND OLD.sealed THEN RAISE EXCEPTION 'sealed campaign is immutable'; END IF;
 ELSE
  cid := CASE WHEN TG_OP='DELETE' THEN OLD.campaign_id ELSE NEW.campaign_id END;
  IF EXISTS(SELECT FROM s02.campaigns WHERE id=cid AND sealed) THEN
   RAISE EXCEPTION 'sealed source is immutable';
  END IF;
  IF TG_OP='UPDATE' AND OLD.campaign_id<>NEW.campaign_id THEN RAISE EXCEPTION 'campaign identity immutable'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION s02.delivery_progress_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' AND (to_jsonb(NEW)-ARRAY['attempts','delivered_at','last_status']) =
                       (to_jsonb(OLD)-ARRAY['attempts','delivered_at','last_status']) THEN RETURN NEW; END IF;
 IF EXISTS(SELECT FROM s02.campaigns WHERE id=CASE WHEN TG_OP='DELETE' THEN OLD.campaign_id ELSE NEW.campaign_id END AND sealed)
 THEN RAISE EXCEPTION 'sealed notification schedule is immutable'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DO $$ DECLARE t TEXT; BEGIN
 FOREACH t IN ARRAY ARRAY['campaigns','orders','components','versions'] LOOP
  IF NOT EXISTS(SELECT FROM pg_trigger WHERE tgrelid=('s02.'||t)::regclass AND tgname='immutable_source') THEN
   EXECUTE format('CREATE TRIGGER immutable_source BEFORE INSERT OR UPDATE OR DELETE ON s02.%I FOR EACH ROW EXECUTE FUNCTION s02.immutable_source()',t);
  END IF;
 END LOOP;
 IF NOT EXISTS(SELECT FROM pg_trigger WHERE tgrelid='s02.deliveries'::regclass AND tgname='delivery_progress_only') THEN
  CREATE TRIGGER delivery_progress_only BEFORE INSERT OR UPDATE OR DELETE ON s02.deliveries FOR EACH ROW EXECUTE FUNCTION s02.delivery_progress_only();
 END IF;
 FOREACH t IN ARRAY ARRAY['orders','components','versions'] LOOP
  EXECUTE format('ALTER TABLE s02.%I ENABLE ROW LEVEL SECURITY',t);
  IF NOT EXISTS(SELECT FROM pg_policy WHERE polrelid=('s02.'||t)::regclass AND polname='source_reader') THEN
   EXECUTE format('CREATE POLICY source_reader ON s02.%I FOR SELECT USING ((current_user=''s02_ebay_reader'' AND source=''ebay_sim'') OR (current_user=''s02_etsy_reader'' AND source=''etsy_sim''))',t);
  END IF;
 END LOOP;
END $$;
GRANT USAGE ON SCHEMA s02 TO s02_ebay_reader,s02_etsy_reader;
GRANT SELECT ON s02.campaigns,s02.orders,s02.components,s02.versions TO s02_ebay_reader,s02_etsy_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA s02 FROM PUBLIC;
RESET ROLE;
INSERT INTO public.schema_migrations(migration_name) VALUES ('marketplace_sim/001_s02_temporal.sql') ON CONFLICT DO NOTHING;
COMMIT;
