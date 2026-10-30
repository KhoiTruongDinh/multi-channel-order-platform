"""Documented review suggestions, not new warehouse states or writable tasks."""
from collections import Counter
from datetime import timezone

CHANNELS = {'internal_web': 'Website', 'ebay_sim': 'eBay', 'etsy_sim': 'Etsy'}
SUGGESTIONS = {
    'Cancellation requested': 'Review cancellation in the source before further fulfillment.',
    'Partial fulfillment': 'Review recorded allocations and remaining items with the fulfillment team.',
    'Fulfillment not started': 'Confirm payment, cancellation and the fulfillment plan in the source. This is not an instruction to ship.',
    'Payment pending': 'Verify payment in the source before proceeding. Do not assume collection is due.',
    'Payment status verification': 'Verify missing or unsupported payment information in the source.',
    'Fulfillment status verification': 'Verify missing or unsupported fulfillment information in the source.',
    'Cancellation status verification': 'Verify cancellation status before deciding on further fulfillment.',
}


def order_key(row):
    return row['source_system'], row['source_account_id'], row['source_order_id']


def channel(row):
    return CHANNELS.get(row['source_system'], row['source_system'])


def state_label(value):
    return 'Not reported' if value is None or value == 'UNKNOWN' else value.replace('_', ' ').capitalize()


def utc(value):
    return value.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if value else 'Not available'


def amount(value, currency):
    return 'Unknown' if value is None else f'{currency} {value:,.2f}'


def review_reasons(order):
    payment, fulfillment, cancellation = (order.get(k) for k in
        ('payment_state', 'fulfillment_state', 'cancellation_state'))
    if cancellation == 'CANCELED':
        return []
    reasons = []
    if cancellation == 'REQUESTED':
        reasons.append('Cancellation requested')
    if cancellation == 'NOT_REQUESTED' and payment == 'PAID':
        if fulfillment == 'PARTIALLY_SHIPPED':
            reasons.append('Partial fulfillment')
        elif fulfillment == 'NOT_STARTED':
            reasons.append('Fulfillment not started')
    if payment == 'UNPAID':
        reasons.append('Payment pending')
    elif payment != 'PAID':
        reasons.append('Payment status verification')
    if fulfillment not in ('NOT_STARTED', 'PARTIALLY_SHIPPED', 'SHIPPED', 'DELIVERED'):
        reasons.append('Fulfillment status verification')
    if cancellation not in ('NOT_REQUESTED', 'REQUESTED', 'CANCELED') and fulfillment in ('NOT_STARTED', 'PARTIALLY_SHIPPED'):
        reasons.append('Cancellation status verification')
    return reasons


def summarize(orders, lines):
    ordered = sorted(orders, key=lambda o: (o['source_created_at'], order_key(o)))
    reviews = [o for o in ordered if review_reasons(o)]
    reasons = Counter(reason for o in reviews for reason in review_reasons(o))
    fulfillment = Counter((channel(o), state_label(o['fulfillment_state'])) for o in ordered
                          if o['cancellation_state'] != 'CANCELED')
    bad_keys = {order_key(l) for l in lines if l['mapping_status'] != 'CONFIRMED' or not l['canonical_variant_id']}
    return dict(reviews=reviews, canceled=[o for o in ordered if o['cancellation_state']=='CANCELED'],
        data_issues=[o for o in ordered if order_key(o) in bad_keys],
        reason_counts=[{'Reason': reason, 'Orders': count} for reason, count in sorted(reasons.items())],
        fulfillment_counts=[{'Channel': ch, 'Fulfillment': state, 'Orders': count}
                            for (ch, state), count in sorted(fulfillment.items())])


def order_rows(orders, include_review=False):
    result = []
    for order in orders:
        row = {'Order': order['source_order_id'], 'Channel': channel(order), 'Account': order['source_account_id'],
               'Created (UTC)': utc(order['source_created_at']), 'Payment': state_label(order['payment_state']),
               'Fulfillment': state_label(order['fulfillment_state']), 'Cancellation': state_label(order['cancellation_state']),
               'Original order total': amount(order['source_order_total_amount'], order['currency'])}
        if include_review:
            reasons = review_reasons(order)
            row.update({'Review reason(s)': '; '.join(reasons),
                        'Suggested review': ' '.join(SUGGESTIONS[r] for r in reasons)})
        result.append(row)
    return result


def availability(snapshot, scopes):
    publications = {p['publication_name']: p for p in snapshot['publications']}
    rows = []
    for health in snapshot['health']:
        if (health['source_system'], health['source_account_id']) not in scopes:
            continue
        publication = publications.get(health['publication_name'])
        published_at = publication['published_at'] if publication else None
        newer_failure = bool(health['last_failed_at'] and
                             (published_at is None or health['last_failed_at'] > published_at))
        rows.append({'Channel': channel(health), 'Account': health['source_account_id'],
                     'Last source check (UTC)': utc(health['last_successful_acquisition_at']),
                     'Report updated (UTC)': utc(published_at),
                     'Data status': 'Not published' if not publication else
                                    'Newer processing failure' if newer_failure else 'Published',
                     'Coverage': 'Not confirmed'})
    return rows
