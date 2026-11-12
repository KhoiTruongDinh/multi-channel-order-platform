"""Strict review, bounded measurement and finite low-rate campaign settings."""
import random


def validate_campaign(value):
    if not isinstance(value,dict) or set(value)-{'timeout_seconds','poll_seconds','seed','fault','measurement','load'}:
        raise ValueError('unknown campaign option')
    value=dict(value)
    for key,default,lo,hi in (('timeout_seconds',1200,30,3600),('poll_seconds',10,2,60),('seed',42,0,2147483647)):
        value.setdefault(key,default)
        if type(value[key]) is not int or not lo<=value[key]<=hi: raise ValueError('invalid campaign '+key)
    value.setdefault('fault',None)
    if value['fault'] is not None:
        f=dict(value['fault']) if isinstance(value['fault'],dict) else {}
        if set(f)-{'kind','start_window_seconds','duration_seconds'} or f.get('kind')!='ebay_pause':
            raise ValueError('only explicit ebay_pause is supported')
        window=f.get('start_window_seconds',[45,75]); duration=f.get('duration_seconds',75)
        if not isinstance(window,list) or len(window)!=2 or any(type(x) is not int for x in window) or not 10<=window[0]<=window[1]<=600:
            raise ValueError('invalid fault start window')
        if type(duration) is not int or not 15<=duration<=180: raise ValueError('invalid fault duration')
        if window[1]+duration>=value['timeout_seconds']: raise ValueError('fault exceeds campaign timeout')
        value['fault']=dict(kind='ebay_pause',start_window_seconds=window,duration_seconds=duration)
    if 'measurement' in value:
        value['measurement']=validate_measurement(value['measurement'])
    if 'load' in value:
        if 'measurement' not in value or value['fault'] is not None:
            raise ValueError('load requires measurement and no campaign outage')
        load=value['load']
        if not isinstance(load,dict) or set(load)-{'min_scheduled_successes','max_drain_seconds'}:
            raise ValueError('unknown load option')
        load=dict(load)
        for key,default,lo,hi in (('min_scheduled_successes',2,1,10),('max_drain_seconds',900,30,1800)):
            load.setdefault(key,default)
            if type(load[key]) is not int or not lo<=load[key]<=hi: raise ValueError('invalid load '+key)
        value['load']=load
    return value


def validate_measurement(value):
    fields={
        'max_orders':(100,1,1000), 'max_source_versions':(500,1,10000),
        'max_generated_bytes':(10485760,1024,104857600),
        'min_free_disk_mb':(2048,256,1048576),
        'max_db_growth_mb':(512,1,10240),
        'max_docker_memory_percent':(90,20,95),
        'max_container_memory_mb':(2400,128,16384),
        'max_pending_sends':(500,1,10000),
        'max_final_observed_delay_seconds':(1200,30,3600)}
    if not isinstance(value,dict) or set(value)-set(fields):
        raise ValueError('unknown measurement option')
    result=dict(value)
    for key,(default,low,high) in fields.items():
        result.setdefault(key,default)
        if type(result[key]) is not int or not low<=result[key]<=high:
            raise ValueError('invalid measurement '+key)
    return result


def timeline(settings):
    f=settings['fault']
    if f is None: return None
    start=random.Random(settings['seed']).randint(*f['start_window_seconds'])
    return dict(kind=f['kind'],start_after_seconds=start,duration_seconds=f['duration_seconds'])
