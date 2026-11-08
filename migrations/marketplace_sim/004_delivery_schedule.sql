\set ON_ERROR_STOP on
BEGIN;
SET ROLE marketplace_owner;
ALTER TABLE s02.deliveries ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'etsy_sim' CHECK(source='etsy_sim');
ALTER TABLE s02.deliveries ADD COLUMN IF NOT EXISTS account_id TEXT NOT NULL DEFAULT '7001' CHECK(account_id='7001');
ALTER TABLE s02.deliveries ADD COLUMN IF NOT EXISTS source_sequence INTEGER CHECK(source_sequence>0);
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_constraint WHERE conrelid='s02.deliveries'::regclass AND conname='delivery_source_version') THEN
  ALTER TABLE s02.deliveries ADD CONSTRAINT delivery_source_version
   FOREIGN KEY(campaign_id,source,account_id,receipt_id,source_sequence)
   REFERENCES s02.versions(campaign_id,source,account_id,order_id,sequence);
 END IF;
END $$;
CREATE TABLE IF NOT EXISTS s02.delivery_schedule (
 campaign_id TEXT NOT NULL, message_id TEXT NOT NULL,
 attempt_no INTEGER NOT NULL CHECK(attempt_no>0), due_at TIMESTAMPTZ NOT NULL,
 send_count INTEGER NOT NULL DEFAULT 0 CHECK(send_count>=0),
 last_attempt_at TIMESTAMPTZ, next_retry_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
 last_http_status INTEGER CHECK(last_http_status BETWEEN 100 AND 599),
 last_error_code TEXT CHECK(last_error_code IN ('TIMEOUT','CONNECT','HTTP','TRANSPORT')),
 PRIMARY KEY(campaign_id,message_id,attempt_no),
 FOREIGN KEY(campaign_id,message_id) REFERENCES s02.deliveries(campaign_id,message_id),
 CHECK((send_count=0 AND last_attempt_at IS NULL) OR (send_count>0 AND last_attempt_at IS NOT NULL)),
 CHECK(completed_at IS NULL OR (send_count>0 AND last_http_status IS NOT NULL
  AND last_http_status BETWEEN 200 AND 299 AND last_error_code IS NULL AND next_retry_at IS NULL))
);
CREATE INDEX IF NOT EXISTS delivery_schedule_pending
 ON s02.delivery_schedule(due_at,campaign_id,message_id,attempt_no) WHERE completed_at IS NULL;
CREATE OR REPLACE FUNCTION s02.schedule_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE d s02.deliveries; at TIMESTAMPTZ;
BEGIN
 IF TG_OP='UPDATE' AND (NEW.campaign_id,NEW.message_id,NEW.attempt_no) IS DISTINCT FROM
   (OLD.campaign_id,OLD.message_id,OLD.attempt_no) THEN RAISE EXCEPTION 'send identity immutable'; END IF;
 IF TG_OP='UPDATE' AND OLD.completed_at IS NOT NULL AND NEW IS DISTINCT FROM OLD THEN
  RAISE EXCEPTION 'completed send immutable';
 END IF;
 IF TG_OP='UPDATE' AND NEW.send_count<OLD.send_count THEN RAISE EXCEPTION 'send counter cannot decrease'; END IF;
 IF EXISTS(SELECT FROM s02.campaigns WHERE id=CASE WHEN TG_OP='DELETE' THEN OLD.campaign_id ELSE NEW.campaign_id END AND sealed) THEN
  IF TG_OP='UPDATE' AND
    (to_jsonb(NEW)-ARRAY['send_count','last_attempt_at','next_retry_at','completed_at','last_http_status','last_error_code']) =
    (to_jsonb(OLD)-ARRAY['send_count','last_attempt_at','next_retry_at','completed_at','last_http_status','last_error_code']) THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'sealed send plan immutable';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 SELECT * INTO d FROM s02.deliveries WHERE campaign_id=NEW.campaign_id AND message_id=NEW.message_id;
 IF d.omitted OR d.source_sequence IS NULL THEN RAISE EXCEPTION 'send requires non-omitted versioned message'; END IF;
 SELECT visible_at INTO at FROM s02.versions WHERE campaign_id=d.campaign_id AND source=d.source
  AND account_id=d.account_id AND order_id=d.receipt_id AND sequence=d.source_sequence;
 IF NEW.due_at<at THEN RAISE EXCEPTION 'send precedes source visibility'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS schedule_guard ON s02.delivery_schedule;
CREATE TRIGGER schedule_guard BEFORE INSERT OR UPDATE OR DELETE ON s02.delivery_schedule
 FOR EACH ROW EXECUTE FUNCTION s02.schedule_guard();
CREATE OR REPLACE FUNCTION s02.validate_delivery_plan() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.sealed AND NOT OLD.sealed AND EXISTS(SELECT FROM s02.local_datasets
   WHERE campaign_id=NEW.id AND coverage#>>'{delivery_plan,version}'='1') THEN
  IF EXISTS(SELECT FROM s02.deliveries d WHERE d.campaign_id=NEW.id AND
    (d.source_sequence IS NULL OR (d.omitted AND EXISTS(SELECT FROM s02.delivery_schedule s
      WHERE s.campaign_id=d.campaign_id AND s.message_id=d.message_id)) OR
     (NOT d.omitted AND NOT EXISTS(SELECT FROM s02.delivery_schedule s
      WHERE s.campaign_id=d.campaign_id AND s.message_id=d.message_id)))) THEN
   RAISE EXCEPTION 'incomplete notification plan';
  END IF;
  IF EXISTS(SELECT FROM s02.delivery_schedule s JOIN s02.deliveries d USING(campaign_id,message_id)
    JOIN s02.versions v ON (v.campaign_id,v.source,v.account_id,v.order_id,v.sequence)=
      (d.campaign_id,d.source,d.account_id,d.receipt_id,d.source_sequence)
    WHERE s.campaign_id=NEW.id AND (d.omitted OR s.due_at<v.visible_at)) OR
    EXISTS(SELECT FROM (SELECT attempt_no,row_number() OVER w AS n,due_at,lag(due_at) OVER w AS prior
      FROM s02.delivery_schedule WHERE campaign_id=NEW.id
      WINDOW w AS (PARTITION BY message_id ORDER BY attempt_no)) x WHERE attempt_no<>n OR due_at<prior) THEN
   RAISE EXCEPTION 'invalid send timeline';
  END IF;
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS validate_delivery_plan ON s02.campaigns;
CREATE TRIGGER validate_delivery_plan BEFORE UPDATE OF sealed ON s02.campaigns
 FOR EACH ROW EXECUTE FUNCTION s02.validate_delivery_plan();
REVOKE ALL ON s02.delivery_schedule FROM PUBLIC,s02_ebay_reader,s02_etsy_reader;
RESET ROLE;
INSERT INTO public.schema_migrations(migration_name) VALUES('marketplace_sim/004_delivery_schedule.sql') ON CONFLICT DO NOTHING;
COMMIT;
