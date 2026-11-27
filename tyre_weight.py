"""Owner-supplied per-tyre estimates; kilograms are independent of EPU factors."""
FACTORS={'passenger':(1,8),'4x4':(2,16),'truck':(5,45)}

def category(name):
    key=str(name).strip().lower()
    if key in ('passenger','car','passenger tyre'):return 'passenger'
    if key in ('4x4','suv','suv/4x4','suv / 4x4'):return '4x4'
    if key in ('truck','truck tyre','truck tires','truck tyres'):return 'truck'
    return 'unknown'

def totals(rows,default_passenger=False):
    counts={key:0 for key in FACTORS};unknown=0
    for name,n in (rows.items() if hasattr(rows,'items') else rows):
        count=max(0,int(n));key=category(name)
        if key=='unknown':unknown+=count
        else:counts[key]+=count
    if default_passenger:counts['passenger']+=unknown
    weights={key:counts[key]*kg for key,(_,kg) in FACTORS.items()}
    epu={key:counts[key]*factor for key,(factor,_) in FACTORS.items()}
    return dict(counts=counts,weights=weights,epu=epu,total_count=sum(counts.values())+(0 if default_passenger else unknown),
                total_kg=sum(weights.values()),total_epu=sum(epu.values()),unknown=unknown)


def add_weight(record,kind):
    """Accumulate class weight alongside the exact same accepted count event."""
    key=category(kind)
    record['estimated_kg']=record.get('estimated_kg',0)+(FACTORS[key][1] if key in FACTORS else FACTORS['passenger'][1])
    record['unknown_weight']=record.get('unknown_weight',0)+int(key=='unknown')

def weight_note(record,compact=False):
    if 'estimated_kg' not in record:return 'Est. weight —'
    kg=record['estimated_kg'];unknown=record.get('unknown_weight',0)
    value=(f'{kg/1000:,.1f} t' if kg>=1000 else f'{kg:,} kg') if compact else f'{kg:,} kg / {kg/1000:,.2f} t'
    return 'Est. '+value+(' *' if unknown else '')
