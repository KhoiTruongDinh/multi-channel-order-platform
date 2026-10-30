"""English multi-channel operations and measured processing workspace."""
from datetime import date, datetime, timedelta
import altair as alt
import streamlit as st
from reports import data
from reports.operations import CHANNELS, SUGGESTIONS, amount, availability, order_key, order_rows, state_label, utc

st.set_page_config(page_title='Multi-channel Operations',page_icon='📦',layout='wide')
page=st.sidebar.radio('Workspace',['Multi-channel Overview','Order Operations','Pipeline Monitoring'],key='workspace')
st.sidebar.button('Refresh data',key='refresh')
st.sidebar.caption('Read-only. Manual refresh; no source actions or cached results.')


def chart(rows,x,y,color,kind='bar'):
    if not rows:
        st.info('No observations in this selection. This is not proof of healthy or complete coverage.')
        return
    safe=[{k:v.isoformat() if isinstance(v,(date,datetime)) else float(v) if hasattr(v,'as_tuple') else v
           for k,v in r.items()} for r in rows]
    for row in safe:
        if 'source_system' in row:
            row['source_system']=CHANNELS.get(row['source_system'],row['source_system'])
    plot=alt.Chart(alt.Data(values=safe))
    plot=plot.mark_line(point=True) if kind=='line' else plot.mark_bar()
    st.altair_chart(plot.encode(x=x,y=y,color=color).interactive(),width='stretch')


try:
    opts=data.options()
except Exception:
    st.error('Database unavailable. No fresh report was loaded. Check report/database configuration.')
    st.stop()
scopes=[data.scope(r) for r in opts['scopes']]
selected=st.sidebar.multiselect('Source / account',scopes,default=scopes,key='scopes',
    format_func=lambda s:s.replace('internal_web','Website').replace('ebay_sim','eBay').replace('etsy_sim','Etsy'))
st.title(page)

if page=='Pipeline Monitoring':
    hours=st.sidebar.selectbox('Actual processing window (UTC)',[1,6,24,168],index=2,key='hours',format_func=lambda h:f'Last {h} hours')
    mode=st.sidebar.selectbox('Measured validation mode',['all','runtime','s01'],key='mode')
    try:
        monitor=data.monitoring(selected,hours,mode)
    except Exception:
        st.error('Monitoring unavailable. No fresh metrics were loaded.')
        st.stop()
    st.caption(f"Read {utc(monitor['now'])} UTC. Actual execution clocks, not simulated source timestamps.")
    st.warning('Coverage unknown. Recorded RUNNING is not a worker heartbeat. No historical duration backfill or ingestion-capacity guarantee.')
    stages=[r for r in monitor['aggregate'] if r['stage'] not in ('source_slot','release_slot')]
    attempts=sum(r['attempts'] for r in stages)
    errors=sum(r['errors'] for r in stages)
    terminal=sum(r['terminal'] for r in stages)
    pending=sum(r['work_count'] for r in monitor['backlog'] if r['state'] in ('PENDING','LEASED','FAILED','DEAD_LETTER'))
    for col,label,value in zip(st.columns(4),['Measured stage attempts','Terminal stage errors','Error rate / terminal attempts','Pending / leased / failed work'],
            [attempts,errors,f'{errors/terminal:.1%} (n={terminal})' if terminal else 'Unknown (n=0)',pending]):
        col.metric(label,value)
    st.subheader('Processing activity by channel')
    st.caption('Five-minute buckets. Physical stage/slot attempts, NOT new unique orders. S01/replay may reprocess existing orders.')
    chart(monitor['series'],'bucket:T','sum(attempts):Q','source_system:N','line')
    st.subheader('Failures and outcomes by channel')
    outcomes={}
    for row in monitor['series']:
        key=(row['source_system'],row['outcome'])
        outcomes[key]=outcomes.get(key,0)+row['attempts']
    chart([dict(source_system=k[0],outcome=k[1],attempts=n) for k,n in outcomes.items()],
          'source_system:N','attempts:Q','outcome:N')
    st.subheader('Which stages are slow?')
    duration=[dict(r,channel_stage=f"{CHANNELS.get(r['source_system'],r['source_system'])} / {r['stage']} (n={r['duration_samples']})")
              for r in monitor['aggregate'] if r['duration_samples']]
    st.caption('p95 in milliseconds; includes slot waiting as separate stages. Sample counts below; no invented SLA thresholds.')
    chart(duration,'p95_ms:Q','channel_stage:N','source_system:N')
    st.subheader('Duration over actual processing time')
    duration_series=[dict(r,source_stage=f"{CHANNELS.get(r['source_system'],r['source_system'])} / {r['stage']} / {r['outcome']}")
                     for r in monitor['series'] if r['mean_ms'] is not None]
    chart(duration_series,'bucket:T','mean_ms:Q','source_stage:N','line')
    st.subheader('Work backlog by channel')
    chart(monitor['backlog'],'source_system:N','work_count:Q','state:N')
    st.caption('Backlog is current recorded work, independent of the time window. Old rows without a recording clock have unknown age.')
    st.dataframe([dict(r,oldest_recorded_age_minutes=(monitor['now']-r['oldest_recorded_at']).total_seconds()/60
        if r['oldest_recorded_at'] else None) for r in monitor['backlog']],hide_index=True)
    st.subheader('Scheduler and DAG visibility')
    if monitor['scheduler']:
        st.dataframe([dict(r,status=data.scheduler_status(r,monitor['now'])) for r in monitor['scheduler']],hide_index=True)
    else:
        st.info('Unknown: no scheduler observations. Start scheduler-observer; no samples is not healthy.')
    st.caption('Paused differs from idle. Samples older than 90s or scheduler heartbeat older than 120s are stale/unknown.')
    with st.expander('Measured samples, denominators and recent audit (max 100 each)'):
        st.dataframe(monitor['aggregate'],hide_index=True)
        for key in ('measurements','runs','tests','exceptions'):
            st.write(key.capitalize())
            st.dataframe(monitor[key],hide_index=True)
        st.caption('Source/account and time filters are applied before LIMIT. FAILED_OR_INTERRUPTED is a batch lifecycle label, not a parsed dbt test result. Audit timestamps may retain S01 scenario time; charts use only new execution telemetry.')
    st.info('Unique newly published orders per processing minute: unavailable (no per-order first-publication ledger). Current order volume is on Overview; attempts must not be relabeled as orders.')
    st.stop()

if not opts['currencies']:
    st.warning('No published orders yet. Source coverage is not confirmed.')
    st.stop()
currency=st.sidebar.selectbox('Currency',opts['currencies'],key='currency')
first,last=opts['dates']['first'],opts['dates']['last']
last=last or date.today()
first=max(first or last,last-timedelta(days=365))
dates=st.sidebar.date_input('Order-created dates (UTC, inclusive)',(first,last),key='dates')
st.sidebar.caption('Default dates describe retained historical orders, not today’s workload. Maximum 366 days.')
if len(dates)!=2:
    st.info('Choose a start and end date.')
    st.stop()
group='all'
reason=''
exact=''
product=''
if page=='Order Operations':
    group=st.selectbox('Worklist',['all','review','canceled','data'],key='group',
        format_func=lambda s:dict(all='All orders',review='Needs review',canceled='Canceled',data='Data issues')[s])
    exact=st.text_input('Exact order ID (optional)',max_chars=256,key='exact').strip()
    reason=st.selectbox('Review reason',['']+list(SUGGESTIONS),key='reason',format_func=lambda s:s or 'All reasons')
else:
    product=st.text_input('Exact canonical product (activity only; optional)',max_chars=256,key='product').strip()
try:
    filters=data.Filters(tuple(selected),currency,*dates,order_id=exact,group=group,reason=reason,product=product)
except ValueError as error:
    st.warning(str(error))
    st.stop()
filter_key=(page,repr(filters))
if st.session_state.get('filter_key')!=filter_key:
    st.session_state.update(filter_key=filter_key,cursor=None,previous=[],selected_order=None)
    st.session_state.pop('inspect_page',None)
try:
    panel=data.business(filters,st.session_state.get('cursor'),st.session_state.get('selected_order'))
except Exception:
    st.error('Database unavailable or query timed out. No fresh business panel was loaded.')
    st.stop()
if panel['reset'] or st.session_state.get('publication_signature',panel['signature'])!=panel['signature']:
    st.session_state.update(cursor=None,previous=[],selected_order=None,publication_signature=panel['signature'])
    st.session_state.pop('inspect_page',None)
    st.info('Publication or filters changed. Pagination and selected order reset; refresh this panel to inspect a current page.')
    # Never combine an old selected detail with the new publication.
    panel['detail']=None
else:
    st.session_state['publication_signature']=panel['signature']
st.caption(f"Report read {utc(panel['metadata']['read_at'])} UTC. All figures use one read-only repeatable-read snapshot. Source creation date ≠ processing time.")
with st.expander('Data availability and source publications'):
    availability_rows=availability(panel,{tuple(s.split(' / ',1)) for s in selected})
    st.dataframe(availability_rows,hide_index=True)
    st.dataframe(panel['publications'],hide_index=True)
    st.caption('A successful check or publication does not prove completeness or an SLA. Last good data remains visible after failed processing.')
if any(r['Data status']!='Published' for r in availability_rows):
    st.warning('Some sources are unpublished or have a newer processing failure. Inspect availability before acting.')
summary=panel['summary']
if page=='Multi-channel Overview':
    st.caption('Published, source/account-scoped unique orders. Includes canceled orders. Amounts are original activity, not recognized revenue.')
    for col,label,value in zip(st.columns(5),['Published orders','Observed versions','Ordered units','Original merchandise','Original order total'],
            [summary['orders'],sum(r['versions'] for r in panel['versions']),panel['lines']['units'],amount(panel['lines']['merchandise'],currency),amount(summary['order_amount'],currency)]):
        col.metric(label,value)
    st.subheader('How much order activity does each channel contribute?')
    channel_metric=st.selectbox('Channel comparison',['orders','units','reviews','versions'],key='channel_metric')
    chart(panel['channels'],'source_system:N',f'{channel_metric}:Q','source_system:N')
    st.dataframe(panel['channels'],hide_index=True)
    st.subheader('Order activity by source creation date')
    chart(panel['series'],'day:T','orders:Q','source_system:N','line')
    st.caption('A single historical fixture day is not a continuity trend. Observed versions are deduplicated versions, not API calls or fabricated events.')
    left,right=st.columns(2)
    with left:
        st.subheader('Observed versions by channel')
        chart(panel['versions'],'source_system:N','versions:Q','source_system:N')
    with right:
        st.subheader('Top 20 products by ordered units')
        chart(panel['products'],'units:Q','product:N','product:N')
        st.caption('Product filter affects only line activity and this chart; order count and order totals do not change.')
else:
    st.caption('Counts and charts cover ALL filtered matches, not just the displayed page. Suggestions are not source actions or overdue alerts.')
    for col,label,value in zip(st.columns(4),['Matching orders','Orders to review','Canceled orders','Data issues'],
            [summary['orders'],summary['reviews'],summary['canceled'],summary['data_issues']]):
        col.metric(label,value)
    left,right=st.columns(2)
    with left:
        st.subheader('Review workload by channel')
        chart(panel['channels'],'source_system:N','reviews:Q','source_system:N')
        chart(panel['fulfillment'],'source_system:N','orders:Q','fulfillment:N')
        st.caption('Fulfillment chart excludes canceled orders. Shipped does not mean delivered.')
    with right:
        st.subheader('Why orders need review')
        chart(panel['reasons'],'orders:Q','reason:N','reason:N')
        st.caption('One order may have multiple reasons; bars are not additive unique-order totals.')
    st.subheader('Order Explorer')
    st.caption('Newest creation first. SQL keyset pagination: at most 50 rows per page, no all-order download or million-ID dropdown. Exact ID search also requires the selected channel/account/date/currency scope.')
    st.dataframe(order_rows(panel['rows'],include_review=True),hide_index=True)
    previous,next_page=st.columns(2)
    if previous.button('Previous page',disabled=not st.session_state['previous'],key='previous_page'):
        st.session_state['cursor']=st.session_state['previous'].pop()
        st.session_state['selected_order']=None
        st.session_state.pop('inspect_page',None)
        st.rerun()
    if next_page.button('Next page',disabled=panel['next_cursor'] is None,key='next_page'):
        st.session_state['previous'].append(st.session_state['cursor'])
        st.session_state['cursor']=panel['next_cursor']
        st.session_state['selected_order']=None
        st.session_state.pop('inspect_page',None)
        st.rerun()
    keys=[order_key(r) for r in panel['rows']]
    selected_order=st.selectbox('Inspect an order from this page only (max 50)',[None]+keys,key='inspect_page',
        format_func=lambda k:'Choose a row from this page' if k is None else f'{CHANNELS.get(k[0],k[0])} / {k[1]} / {k[2]}')
    if selected_order!=st.session_state['selected_order']:
        st.session_state['selected_order']=selected_order
        st.rerun()
    detail=panel['detail']
    if detail:
        order=detail['order']
        st.subheader(f"Order {order['source_order_id']}")
        for col,label,field in zip(st.columns(3),['Payment','Fulfillment','Cancellation'],['payment_state','fulfillment_state','cancellation_state']):
            col.metric(label,state_label(order[field]))
        for r in order['review_reasons']:
            st.info(f'{r}: {SUGGESTIONS[r]}')
        st.caption(f"Original total {amount(order['source_order_total_amount'],currency)}. Source updated {utc(order['source_updated_at'])} UTC. Read-only; act in the source system.")
        for name,label in [('lines','Order lines'),('history','Actually observed history'),('allocations','Recorded line shipment allocations')]:
            with st.expander(label,expanded=name=='lines'):
                st.dataframe(detail[name],hide_index=True)
                if detail[name+'_truncated']:
                    st.warning('Showing the first 100 records only; this is not complete history.')
                if not detail[name]:
                    st.info('No retained evidence available. Missing allocations do not prove nothing shipped.')
        st.caption('Only retained eBay line allocations are available. Etsy order-level shipping is not a parcel-to-line allocation. Unknown is not false; no refund or unobserved event is inferred.')
