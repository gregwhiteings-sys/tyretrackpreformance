"""Owner-supplied per-tyre estimates; kilograms are independent of EPU factors."""
FACTORS={'passenger':(1,8),'4x4':(2,16),'truck':(5,45)}

def category(name):
    key=str(name).strip().lower()
    if key in ('passenger','car','passenger tyre'):return 'passenger'
    if key in ('4x4','suv','suv/4x4','suv / 4x4'):return '4x4'
    if key in ('truck','truck tyre','truck tires','truck tyres'):return 'truck'
    return 'unknown'

def totals(rows):
    counts={key:0 for key in FACTORS};unknown=0
    for name,n in (rows.items() if hasattr(rows,'items') else rows):
        count=max(0,int(n));key=category(name)
        if key=='unknown':unknown+=count
        else:counts[key]+=count
    weights={key:counts[key]*kg for key,(_,kg) in FACTORS.items()}
    epu={key:counts[key]*factor for key,(factor,_) in FACTORS.items()}
    return dict(counts=counts,weights=weights,epu=epu,total_count=sum(counts.values())+unknown,
                total_kg=sum(weights.values()),total_epu=sum(epu.values()),unknown=unknown)
