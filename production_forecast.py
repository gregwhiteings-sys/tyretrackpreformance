"""Constant-cost forecast from the existing committed production snapshot.
Average pace includes stops and breaks; estimates are not guaranteed output.
Matches current weekday 05:00–17:05 Brisbane counting schedule.
"""
import math

def forecast_text(now, target, data, test_mode=False):
    if test_mode: return 'Production forecast paused during video/manual tests'
    if not target: return 'Set a daily target to enable the shift forecast'
    if now.weekday() >= 5: return f'Target: {target:,} tyres · No scheduled production today'
    start = now.replace(hour=5, minute=0, second=0, microsecond=0)
    end = now.replace(hour=17, minute=5, second=0, microsecond=0)
    if now < start: return f'Target: {target:,} tyres · Shift starts at 05:00 Brisbane'
    if not data or data.get('day') != now.date().isoformat() or data.get('hour') != now.hour:
        return f'Target: {target:,} tyres · Waiting for current production totals'
    total = max(0, int(data['daily']))
    remaining = max(0, target-total)
    if now >= end:
        return f'Shift ended · {total:,} / {target:,} tyres · ' + ('Target achieved' if not remaining else f'{remaining:,} short of target')
    if not remaining: return f'Target achieved · {total:,} / {target:,} tyres'
    elapsed = (now-start).total_seconds()/3600
    left = (end-now).total_seconds()/3600
    needed = math.ceil(remaining/left)
    if elapsed < .25:
        return f'Target: {target:,} · Need {needed:,} tyres/hour · Forecast available after 15 minutes'
    projected = round(total/elapsed * ((end-start).total_seconds()/3600))
    gap = projected-target
    status = f'{abs(gap):,} ' + ('above target' if gap >= 0 else 'short of target')
    return (f'Target: {target:,} · Estimated finish: {projected:,} ({status})\n'
            f'Need {needed:,} tyres/hour · Assumes average shift pace continues, including stops')
