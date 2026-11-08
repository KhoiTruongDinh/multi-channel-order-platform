"""Pure, bounded per-order notification plans; never changes source payloads."""
from datetime import timedelta
from tools.s02_data.config import parse_time, stream
from test_support.s02_inputs import stamp
from test_support.s02_plan import literal


def plan(batch, config, reordered=False):
    settings = config['channels']['etsy_sim'].get('delivery_plan')
    if not settings or batch[0]['source'] != 'etsy_sim':
        return []
    rng = stream(settings['seed'], 'etsy_sim', batch[0]['order_id'], 'delivery')
    messages = []
    for event in batch:
        at = parse_time(event['visible_at']) + timedelta(seconds=rng.randint(*settings['delay_seconds']))
        messages.append(dict(sequence=event['sequence'], due_at=at, event=event))
    if reordered:
        if len(messages) < 2 or not batch[-1]['payload']['is_shipped'] or not batch[0]['notify']:
            raise ValueError('reorder requires a non-omitted paid/shipped lifecycle')
        messages[0]['due_at'] = messages[-1]['due_at'] + timedelta(seconds=rng.randint(*settings['late_gap_seconds']))
    rows = []
    for message in messages:
        event = message['event']
        if not event['notify']:
            continue
        at = message['due_at']
        count = settings['repeat_count'] if event['duplicate'] else 1
        for attempt in range(1, count + 1):
            if attempt > 1:
                at += timedelta(seconds=rng.randint(*settings['repeat_gap_seconds']))
            rows.append(dict(sequence=event['sequence'], attempt_no=attempt, due_at=stamp(at)))
    return rows


def sql(identity, batch, rows):
    statements = []
    for event in batch:
        message = f"s02-{identity}-{event['order_id']}-{event['sequence']}"
        statements.append('UPDATE s02.deliveries SET source_sequence=' + str(event['sequence']) +
                          ' WHERE campaign_id=' + literal(identity) + ' AND message_id=' + literal(message) + ';')
    for row in rows:
        message = f"s02-{identity}-{batch[0]['order_id']}-{row['sequence']}"
        statements.append('INSERT INTO s02.delivery_schedule(campaign_id,message_id,attempt_no,due_at) VALUES (' +
                          ','.join((literal(identity), literal(message), str(row['attempt_no']), literal(row['due_at']))) + ');')
    return statements
