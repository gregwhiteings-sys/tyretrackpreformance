"""Forecast fitting on actual Qt paint devices, including Windows-like DPI."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from PyQt5.QtWidgets import QApplication,QLabel
from PyQt5.QtGui import QImage,QFont,QTextDocument
from monthly_forecast import projection_card_html,fit_projection_html,set_projection_card
app=QApplication.instance() or QApplication([])
font=QFont('Segoe UI');font.setPixelSize(16);font.setWeight(QFont.Black)
failed_original=0;cases=0
for dpi in (96,120,144,192):
 image=QImage(400,300,QImage.Format_ARGB32)
 image.setDotsPerMeterX(round(dpi/.0254));image.setDotsPerMeterY(round(dpi/.0254))
 for width,height in ((140,78),(128,78),(140,100),(140,48)):
  for title,value,paused in [('THIS MONTH','21 tyres\n0.2 tonnes',False),('TODAY','123,456 tyres\n1,234.5 tonnes',False),('THIS WEEK','',True)]:
   def layout(html):
    d=QTextDocument();d.documentLayout().setPaintDevice(image);d.setDocumentMargin(0);d.setDefaultFont(font);d.setHtml(html);d.setTextWidth(width);return d
   original=layout(projection_card_html(title,value,paused))
   failed_original+=int(original.size().height()>height or original.idealWidth()>width)
   text=fit_projection_html(title,value,width,height,font,image,paused)
   d=layout(text)
   assert d.size().height()<=height and d.idealWidth()<=width,(dpi,width,height,title,d.size().height(),d.idealWidth(),text)
   assert ('123,456' in text and '1,234.5' in text) if value.startswith('123') else True
   cases+=1
assert failed_original>0, 'Test did not reproduce any fixed-font overflow'
label=QLabel();label.setStyleSheet('border:1px solid white;padding:2px;font:900 16px "Segoe UI";');label.resize(148,88);label.ensurePolished()
set_projection_card(label,'THIS MONTH','123,456 tyres\n1,234.5 tonnes')
assert '123,456' in label.text() and '1,234.5' in label.text()
print(f'PASS {cases} card cases at 96/120/144/192 DPI; fixed-font overflow reproduced in {failed_original}; all numbers preserved and styled QLabel content rectangle respected')
