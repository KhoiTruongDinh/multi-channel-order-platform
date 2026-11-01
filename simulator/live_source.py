"""Live source timestamp translation; no warehouse or expectation dependencies."""
from datetime import datetime, timedelta

ISO_TIMES = frozenset(('created_at','updated_at','occurred_at','requested_at','resolved_at',
    'creationDate','lastModifiedDate','shippedDate'))
EPOCH_TIMES = frozenset(('created_timestamp','updated_timestamp','paid_timestamp',
    'shipped_timestamp','shipment_notification_timestamp'))


def translate(value, seconds):
    """Copy a source document, shifting only contracted business timestamp fields."""
    if isinstance(value,list):
        return [translate(v,seconds) for v in value]
    if not isinstance(value,dict):
        return value
    out={}
    for key,item in value.items():
        if item is not None and key in ISO_TIMES:
            out[key]=(datetime.fromisoformat(item.replace('Z','+00:00'))+
                      timedelta(seconds=seconds)).isoformat()
        elif item is not None and key in EPOCH_TIMES:
            out[key]=item+seconds
        else:
            out[key]=translate(item,seconds)
    return out
