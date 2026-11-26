"""Real Qt footer geometry and read-only update/error/status behavior."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from PyQt5.QtWidgets import QApplication,QWidget,QVBoxLayout,QLabel
from PyQt5.QtCore import Qt
from review_cards import ReviewCards
app=QApplication.instance() or QApplication([])
host=QWidget();layout=QVBoxLayout(host);layout.setContentsMargins(0,0,0,0)
clicked=[];cards=ReviewCards(lambda:clicked.append(True));layout.addWidget(cards);host.show()
result={'automatic_overlap_added':4,'assisted_counts':{'passenger':1935,'4x4':297,'truck':12,'unknown':1,'uncertain_or_unmeasured':2},'original_counts':{'passenger':1955}}
cards.show_result(result)
assert cards.additions.text()=='+4' and cards.values['passenger'].text()=='1,935'
assert cards.values['4x4'].text()=='297' and cards.values['truck'].text()=='12' and cards.values['unknown'].text()=='3'
for style in ['Fusion','Windows']:
 app.setStyle(style)
 for width in [640,720,880]:
  host.resize(width,168)
  for _ in range(4):app.processEvents()
  assert abs(cards.cards[0].width()-cards.cards[1].width())<=1
  assert cards.cards[0].height()==cards.cards[1].height()==168
  for card in cards.cards:
   for label in card.findChildren(QLabel):
    at=label.mapTo(card,label.rect().topLeft())
    assert 0<=at.x() and at.x()+label.width()<=card.width(),(style,width,label.text())
    assert 0<=at.y() and at.y()+label.height()<=card.height(),(style,width,label.text(),at.y(),label.height())
    assert label.fontMetrics().horizontalAdvance(label.text())<=label.contentsRect().width(),(style,width,label.text(),label.width())
cards.show_status('OVERLAP V8 OFF: model unavailable');assert cards.status.text().startswith('Fault')
cards.show_status('OVERLAP +1 NOT SAVED: disk full');assert cards.status.text().startswith('Save failed')
cards.set_enabled(False);assert cards.status.text().startswith('Off')
cards.set_enabled(True);assert '65%' in cards.status.text()
cards.show_result({'error':'database busy'});assert cards.additions.text()=='—' and all(v.text()=='—' for v in cards.values.values())
cards.show_result(result);assert cards.additions.text()=='+4' and cards.included.text().startswith('Already included')
cards.review_button.click();assert clicked==[True]
assert result['automatic_overlap_added']==4 and result['original_counts']=={'passenger':1955}
assert not any('Measured' in w.text() or 'V8' in w.text() for w in cards.findChildren(QLabel))
host.close()
print('PASS equal footer cards at 3 widths/2 styles, observe-only class values, included +1 subtotal, faults, error recovery and review action; no count writes')
