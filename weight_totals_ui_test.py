"""Real dashboard: all added weight readings fit alongside unchanged counts."""
from pathlib import Path
source=Path('weekday_dashboard_test.py').read_text()
needle='    assert w.hourly_strip.isVisible() and w.weekday_strip.isVisible()'
extra='''
    from PyQt5.QtGui import QTextDocument
    w.refresh_month_week_totals()
    for block in w.dashboard_hour_blocks+w.dashboard_day_blocks+[b for b in w.dashboard_week_blocks if b.isVisible()]:
     assert 'Est.' in block.text(),block.text()
     doc=QTextDocument();doc.documentLayout().setPaintDevice(block);doc.setDocumentMargin(0);doc.setDefaultFont(block.font());doc.setHtml(block.text());doc.setTextWidth(block.contentsRect().width()-4)
     assert doc.size().height()<=block.contentsRect().height()-4,(style,width,height,block.text(),doc.size().height(),block.contentsRect().height())
    assert '40 kg' in w.dashboard_day_blocks[0].text(),w.dashboard_day_blocks[0].text()
    assert '24 kg' in w.dashboard_day_blocks[1].text()
    assert '16 kg' in w.dashboard_day_blocks[2].text()
'''
assert needle in source;source=source.replace(needle,needle+extra)
source=source.replace('weekday_dashboard_preview.png','weight_dashboard_preview.png')
exec(compile(source,'weight_totals_real_ui_fixture','exec'),{'__file__':str(Path('weekday_dashboard_test.py').resolve())})
print('PASS real hourly/daily/weekly weight totals, unchanged tyre counts, all text fits 3 resolutions and 2 styles')
