"""Airflow DAG scheduler gate: production factory, one configured fault."""
from orchestration.dags.polling_orders import website_polling
import os

if os.environ.get('DELTA_SCHEDULER_ALL_SOURCES')=='true':
    from orchestration.dags.polling_orders import ebay_polling
    from orchestration.dags.etsy_orders import etsy_inbox, etsy_recovery

fault=os.environ.get('DELTA_SCHEDULER_ALL_SOURCES')!='true'
website_polling.params['fault_after_freeze_once'] = fault
for operator in website_polling.tasks:
    # Airflow merges task params over DAG params; configure both explicitly.
    operator.params['fault_after_freeze_once'] = fault
