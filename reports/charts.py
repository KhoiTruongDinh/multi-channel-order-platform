"""Review charts aggregate orders, never line-joined order amounts."""
import altair as alt


def fulfillment_chart(rows):
    return alt.Chart(alt.Data(values=rows)).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X('Channel:N', title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Orders:Q', title='Non-canceled orders', axis=alt.Axis(tickMinStep=1)),
        color=alt.Color('Fulfillment:N', scale=alt.Scale(
            domain=['Not started','Partially shipped','Shipped','Delivered','Not reported'],
            range=['#94a3b8','#f59e0b','#2563eb','#059669','#64748b']), legend=alt.Legend(orient='bottom')),
        tooltip=['Channel:N','Fulfillment:N','Orders:Q']).properties(height=270)


def reasons_chart(rows):
    base = alt.Chart(alt.Data(values=rows)).encode(
        y=alt.Y('Reason:N', sort='-x', title=None),
        x=alt.X('Orders:Q', title='Orders with this reason', axis=alt.Axis(tickMinStep=1)),
        tooltip=['Reason:N','Orders:Q'])
    return (base.mark_bar(color='#d97706', cornerRadiusEnd=3) +
            base.mark_text(align='left', dx=5).encode(text='Orders:Q')).properties(height=270)
