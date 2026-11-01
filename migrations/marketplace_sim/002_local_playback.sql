\set ON_ERROR_STOP on
BEGIN;
SET ROLE marketplace_owner;
CREATE TABLE IF NOT EXISTS s02.local_datasets (
 campaign_id TEXT PRIMARY KEY REFERENCES s02.campaigns(id),
 name TEXT NOT NULL UNIQUE CHECK(btrim(name)<>''),
 state TEXT NOT NULL CHECK(state IN ('LOADING','READY')),
 "references" JSONB NOT NULL CHECK(jsonb_typeof("references")='object'),
 coverage JSONB NOT NULL CHECK(jsonb_typeof(coverage)='object')
);
CREATE TABLE IF NOT EXISTS s02.website_versions (
 campaign_id TEXT NOT NULL REFERENCES s02.local_datasets(campaign_id),
 order_id TEXT NOT NULL, sequence INTEGER NOT NULL CHECK(sequence>0),
 visible_at TIMESTAMPTZ NOT NULL, payload JSONB NOT NULL CHECK(jsonb_typeof(payload)='object'),
 PRIMARY KEY(campaign_id,order_id,sequence), UNIQUE(campaign_id,order_id,visible_at)
);
CREATE INDEX IF NOT EXISTS website_due ON s02.website_versions(campaign_id,visible_at);
CREATE TABLE IF NOT EXISTS s02.playback (
 singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(singleton),
 campaign_id TEXT NOT NULL REFERENCES s02.local_datasets(campaign_id),
 mode TEXT NOT NULL CHECK(mode IN ('realtime','replay')),
 logical_start TIMESTAMPTZ NOT NULL, real_start TIMESTAMPTZ NOT NULL,
 stopped_at TIMESTAMPTZ
);
CREATE OR REPLACE FUNCTION s02.local_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE cid TEXT;
BEGIN
 IF TG_TABLE_NAME='local_datasets' THEN
  IF TG_OP<>'INSERT' AND OLD.state='READY' THEN RAISE EXCEPTION 'ready dataset immutable'; END IF;
 ELSE
  cid:=CASE WHEN TG_OP='DELETE' THEN OLD.campaign_id ELSE NEW.campaign_id END;
  IF EXISTS(SELECT FROM s02.local_datasets WHERE campaign_id=cid AND state='READY') THEN
   RAISE EXCEPTION 'ready Website plan immutable';
  END IF;
  IF TG_OP='UPDATE' AND OLD.campaign_id<>NEW.campaign_id THEN RAISE EXCEPTION 'dataset identity immutable'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_trigger WHERE tgrelid='s02.local_datasets'::regclass AND tgname='local_immutable') THEN
  CREATE TRIGGER local_immutable BEFORE INSERT OR UPDATE OR DELETE ON s02.local_datasets FOR EACH ROW EXECUTE FUNCTION s02.local_immutable();
 END IF;
 IF NOT EXISTS(SELECT FROM pg_trigger WHERE tgrelid='s02.website_versions'::regclass AND tgname='local_immutable') THEN
  CREATE TRIGGER local_immutable BEFORE INSERT OR UPDATE OR DELETE ON s02.website_versions FOR EACH ROW EXECUTE FUNCTION s02.local_immutable();
 END IF;
END $$;
CREATE OR REPLACE VIEW s02.playback_clock AS
 SELECT p.campaign_id,p.mode,p.logical_start,p.real_start,p.stopped_at,
 CASE WHEN p.mode='realtime' THEN coalesce(p.stopped_at,statement_timestamp())
 ELSE p.logical_start+(coalesce(p.stopped_at,statement_timestamp())-p.real_start) END AS logical_now
 FROM s02.playback p JOIN s02.local_datasets d USING(campaign_id) WHERE d.state='READY';
GRANT SELECT ON s02.playback,s02.playback_clock TO s02_ebay_reader,s02_etsy_reader;
REVOKE ALL ON s02.local_datasets FROM s02_ebay_reader,s02_etsy_reader;
GRANT SELECT(campaign_id,name,state) ON s02.local_datasets TO s02_ebay_reader,s02_etsy_reader;
REVOKE ALL ON s02.local_datasets,s02.website_versions,s02.playback FROM PUBLIC;
RESET ROLE;
INSERT INTO public.schema_migrations(migration_name) VALUES ('marketplace_sim/002_local_playback.sql') ON CONFLICT DO NOTHING;
COMMIT;
