\set ON_ERROR_STOP on
BEGIN;
SET ROLE marketplace_owner;
CREATE TABLE IF NOT EXISTS s02.live_batches (
 campaign_id TEXT PRIMARY KEY REFERENCES s02.local_datasets(campaign_id),
 published_at TIMESTAMPTZ NOT NULL,
 shift_seconds BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS s02.live_website_progress (
 campaign_id TEXT NOT NULL, order_id TEXT NOT NULL, sequence INTEGER NOT NULL,
 PRIMARY KEY(campaign_id,order_id),
 FOREIGN KEY(campaign_id,order_id,sequence) REFERENCES s02.website_versions(campaign_id,order_id,sequence)
);
CREATE OR REPLACE FUNCTION s02.live_admission() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'live admission immutable'; END IF;
 IF NOT EXISTS(SELECT FROM s02.local_datasets d JOIN s02.campaigns c ON c.id=d.campaign_id
               WHERE d.campaign_id=NEW.campaign_id AND d.state='READY' AND c.sealed)
 THEN RAISE EXCEPTION 'live admission requires sealed READY data'; END IF;
 IF EXISTS(SELECT FROM s02.orders n JOIN s02.orders o USING(source,account_id,order_id)
           JOIN s02.live_batches b ON b.campaign_id=o.campaign_id WHERE n.campaign_id=NEW.campaign_id)
 OR EXISTS(SELECT FROM s02.website_versions n JOIN s02.website_versions o USING(order_id)
           JOIN s02.live_batches b ON b.campaign_id=o.campaign_id WHERE n.campaign_id=NEW.campaign_id)
 THEN RAISE EXCEPTION 'live source identity collision'; END IF;
 RETURN NEW;
END $$;
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_trigger WHERE tgrelid='s02.live_batches'::regclass AND tgname='live_admission') THEN
  CREATE TRIGGER live_admission BEFORE INSERT OR UPDATE OR DELETE ON s02.live_batches
  FOR EACH ROW EXECUTE FUNCTION s02.live_admission();
 END IF;
END $$;
REVOKE ALL ON s02.live_batches FROM PUBLIC;
REVOKE ALL ON s02.live_website_progress FROM PUBLIC;
GRANT SELECT ON s02.live_batches TO s02_ebay_reader,s02_etsy_reader;
RESET ROLE;
INSERT INTO public.schema_migrations(migration_name) VALUES ('marketplace_sim/003_live_batches.sql') ON CONFLICT DO NOTHING;
COMMIT;
