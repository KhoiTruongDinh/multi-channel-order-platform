"""Strict stdlib workload configuration and weighted local-time sampling."""
import hashlib
import json
import math
import random
import re
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SOURCES = ('internal_web','ebay_sim','etsy_sim')
BRANCHES = {'internal_web': {'pending':0,'request':1,'cancel':2},
            'ebay_sim': {'pending':0,'partial':1,'ship':2},
            'etsy_sim': {'pending':0,'ship':1}}


def parse_time(value):
    at = datetime.fromisoformat(value.replace('Z','+00:00'))
    if at.tzinfo is None:
        raise ValueError('timestamps require an explicit UTC offset')
    return at.astimezone(timezone.utc).replace(microsecond=0)


def zone(name):
    # These two zones have no DST in the supported 2026+ workload range.
    if name in ('Asia/Bangkok','Asia/Ho_Chi_Minh'):
        return timezone(timedelta(hours=7))
    if name == 'UTC':
        return timezone.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        raise ValueError('timezone unavailable; install tzdata or use UTC/Asia/Bangkok') from None


def stream(seed, source, index, purpose):
    raw=json.dumps([seed,source,index,purpose],separators=(',',':')).encode()
    return random.Random(int.from_bytes(hashlib.sha256(raw).digest(),'big'))


def exact_keys(value, allowed, label):
    if not isinstance(value,dict) or set(value)-set(allowed):
        raise ValueError('unsupported fields in '+label)


def integer(value, low, high):
    if type(value) is not int or not low<=value<=high:
        raise ValueError(f'expected integer {low}..{high}')
    return value


def segments(start,end,tz,peaks):
    """UTC segments weighted by local hour; O(days*windows), never O(seconds)."""
    windows=[]
    for p in peaks:
        exact_keys(p,('start','end','weight'),'peak')
        def minute(s):
            if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',s):
                raise ValueError('peak hours require HH:MM')
            h,m=map(int,s.split(':')); return h*60+m
        a,b=minute(p['start']),minute(p['end'])
        weight=p['weight']
        if isinstance(weight,bool) or not isinstance(weight,(int,float)) or not math.isfinite(weight) or weight<=0 or a==b:
            raise ValueError('invalid peak weight/empty window')
        windows.extend([(a,b,weight)] if a<b else [(a,1440,weight),(0,b,weight)])
    windows.sort()
    if any(a[1]>b[0] for a,b in zip(windows,windows[1:])):
        raise ValueError('overlapping peak windows')
    cuts={start,end}
    day=start.astimezone(tz).date()
    last=end.astimezone(tz).date()
    while day<=last:
        for m in {0,1440,*[x for a,b,_ in windows for x in (a,b)]}:
            at=(datetime.combine(day,datetime.min.time(),tzinfo=tz)+timedelta(minutes=m)).astimezone(timezone.utc)
            if start<at<end: cuts.add(at)
        day+=timedelta(days=1)
    out=[]
    for a,b in zip(sorted(cuts),sorted(cuts)[1:]):
        middle=(a+(b-a)/2).astimezone(tz)
        minute=middle.hour*60+middle.minute
        weight=next((w for lo,hi,w in windows if lo<=minute<hi),1)
        seconds=int((b-a).total_seconds())
        if seconds: out.append((a,seconds,weight))
    return out


def sample_time(parts,rng):
    masses=[n*w for _,n,w in parts]
    pick=rng.random()*sum(masses)
    for (at,n,_),mass in zip(parts,masses):
        if pick<mass: return at+timedelta(seconds=rng.randrange(n))
        pick-=mass
    raise ValueError('empty time range')


def validate(value):
    value=json.loads(json.dumps(value))
    exact_keys(value,('dataset','timezone','start_at','end_at','duration_minutes','order_seed','event_seed','profile','channels'),'workload')
    if not re.fullmatch('[a-z][a-z0-9-]{2,60}',value['dataset']):
        raise ValueError('dataset must be a lowercase name, 3..61 characters')
    value.setdefault('profile','normal')
    if value['profile'] not in ('normal','coverage','faults'): raise ValueError('invalid profile')
    duration=integer(value.get('duration_minutes',300),1,366*24*60)
    # Resolve once before generation; persist these concrete timestamps in the manifest.
    if value.get('start_at') in (None,''):
        value['start_at']=datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if value.get('end_at') in (None,''):
        value['end_at']=(parse_time(value['start_at'])+timedelta(minutes=duration)).isoformat()
    for key in ('order_seed','event_seed'):
        value[key]=integer(value.get(key,secrets.randbelow(2147483648)),0,2147483647)
    if set(value['channels'])!=set(SOURCES): raise ValueError('declare all three channels explicitly')
    for source,c in value['channels'].items():
        exact_keys(c,('orders','start_at','end_at','timezone','peak_hours','basket','branches','delay_seconds','required','notifications'),'channel '+source)
        integer(c['orders'],0,100000)
        c.setdefault('start_at',value['start_at']); c.setdefault('end_at',value['end_at'])
        c.setdefault('timezone',value.get('timezone','UTC')); c.setdefault('peak_hours',[])
        start,end=map(parse_time,(c['start_at'],c['end_at']))
        if start<parse_time('2026-01-08T00:00:00Z') or not 1<=(end-start).total_seconds()<=366*86400:
            raise ValueError('range must be 1s..366 days, after reference creation')
        segments(start,end,zone(c['timezone']),c['peak_hours'])
        c.setdefault('basket',dict(lines_min=1,lines_max=8,quantity_min=1,quantity_max=5))
        b=c['basket']; exact_keys(b,('lines_min','lines_max','quantity_min','quantity_max'),'basket')
        integer(b['lines_min'],1,30); integer(b['lines_max'],b['lines_min'],30)
        # Website source writer supports up to ten lines per transaction.
        if b['lines_max']>8: raise ValueError('current supported basket limit is eight lines')
        integer(b['quantity_min'],1,100); integer(b['quantity_max'],b['quantity_min'],100)
        c.setdefault('branches',{'pending':0.25, 'cancel' if source=='internal_web' else 'ship':0.75})
        if set(c['branches'])-set(BRANCHES[source]) or not c['branches']: raise ValueError('unsupported lifecycle branch')
        weights=list(c['branches'].values())
        if any(isinstance(w,bool) or not isinstance(w,(int,float)) or not math.isfinite(w) or w<0 for w in weights) or sum(weights)<=0:
            raise ValueError('invalid branch weights')
        c.setdefault('delay_seconds',[60,3600]); lo,hi=c['delay_seconds']
        integer(lo,1,86400*30); integer(hi,lo,86400*30)
        c.setdefault('required',{})
        if set(c['required'])-set(BRANCHES[source]): raise ValueError('unsupported required case')
        for branch,n in c['required'].items():
            integer(n,0,c['orders'])
            if n and BRANCHES[source][branch]*hi>=(end-start).total_seconds():
                raise ValueError('range too short for required lifecycle: '+branch)
        if sum(c['required'].values())>c['orders']: raise ValueError('required quotas exceed order count')
        if source=='ebay_sim' and b['lines_min']<2 and (c['required'].get('partial',0) or c['branches'].get('partial',0)):
            raise ValueError('partial branch currently requires lines_min >= 2')
        c.setdefault('notifications',{'omit':0,'duplicate':0})
        exact_keys(c['notifications'],('omit','duplicate'),'notifications')
        c['notifications'].setdefault('omit',0)
        c['notifications'].setdefault('duplicate',0)
        for n in c['notifications'].values(): integer(n,0,c['orders'])
        if any(c['notifications'].values()) and (source!='etsy_sim' or value['profile']!='faults'):
            raise ValueError('notification faults require Etsy and explicit faults profile')
        if sum(c['notifications'].values())>c['orders']: raise ValueError('delivery quotas exceed orders')
    return value
