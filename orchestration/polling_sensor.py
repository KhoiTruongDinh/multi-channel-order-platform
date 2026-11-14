"""Live-only sensor: exit75 releases the worker without consuming a retry."""
import subprocess

from airflow.sdk import BaseSensorOperator
from airflow.sdk.exceptions import AirflowFailException


class PollingCycleSensor(BaseSensorOperator):
    template_fields=('source','collection_mode')

    def __init__(self,*,source=None,collection_mode=None,**kwargs):
        super().__init__(mode='reschedule',poke_interval=15,timeout=900,**kwargs)
        self.source=source
        self.collection_mode=collection_mode

    def poke(self,context):
        # DAG invoke helpers keep source-specific CLI args/context in one place.
        if self.collection_mode:
            from orchestration.dags.etsy_orders import invoke
            return invoke(self.collection_mode,nonblocking=True,context=context)
        from orchestration.dags.polling_orders import invoke
        return invoke(self.source,nonblocking=True,context=context)


def command_result(command,nonblocking=False):
    result=subprocess.run(command,check=False)
    if result.returncode==42:
        raise AirflowFailException('Durable polling stage budget exhausted')
    if nonblocking and result.returncode==75:
        return False
    result.check_returncode()
    return True
