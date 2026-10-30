"""Safe operator-only pixels; JPEG work/network off GUI; opt-in and rate limits."""
import os,json,tempfile,threading,time,sys,types
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QImage,QColor,QPainter
from PyQt5.QtCore import QRect,QTimer
from unittest.mock import MagicMock
from web_dashboard import operator_image,Publisher,ImagePublisher,URL
qt=QApplication.instance() or QApplication([])
for ratio in (1,2):
 full=QImage(800*ratio,500*ratio,QImage.Format_RGB32);full.setDevicePixelRatio(ratio);full.fill(QColor('red'))
 painter=QPainter(full);painter.fillRect(QRect(50,100,200,100),QColor('green'));painter.end()
 safe=operator_image(full,[QRect(50,100,200,100)])
 assert safe.pixelColor(100*ratio,150*ratio).name()==QColor('green').name()
 assert safe.pixelColor(600*ratio,300*ratio).name()=='#07111e'
 assert safe.pixelColor(20*ratio,250*ratio).name()=='#07111e'
with tempfile.TemporaryDirectory() as folder:
 clock=[0];stats=Publisher(Path(folder)/'web.json');stats.config=dict(schema=1,url=URL,token='test-only-'+'x'*40,enabled=True,snapshot_enabled=False)
 pub=ImagePublisher(stats,clock=lambda:clock[0]);im=QImage(1600,1000,QImage.Format_RGB32);im.fill(QColor('green'))
 assert not pub.request(im,'2026-10-31T00:00:00.000Z')
 stats.config['snapshot_enabled']=True;entered=threading.Event();release=threading.Event();calls=[]
 def opener(req,timeout):
  calls.append((threading.get_ident(),req));entered.set();assert release.wait(3)
  response=MagicMock();response.__enter__.return_value.status=200;return response
 stats.opener=opener
 assert pub.request(im,'2026-10-31T00:00:00.000Z');assert entered.wait(2)
 fired=[];QTimer.singleShot(0,lambda:fired.append(True));qt.processEvents();assert fired
 assert not pub.request(im,'2026-10-31T00:00:00.000Z')
 release.set();pub.thread.join(3);assert pub.status=='Dashboard snapshot sent successfully'
 tid,req=calls[0];assert tid!=threading.get_ident();assert req.data[:2]==b'\xff\xd8' and len(req.data)<512*1024
 decoded=QImage.fromData(req.data,'JPEG');assert decoded.width()<=1280 and decoded.height()<=960
 assert req.get_header('X-captured-at')=='2026-10-31T00:00:00.000Z'
 assert not pub.request(im,'2026-10-31T00:00:00.000Z')
 clock[0]=31;stats.opener=MagicMock(side_effect=OSError('private detail'));assert pub.request(im,'2026-10-31T00:00:31.000Z');pub.thread.join(3)
 assert 'private detail' not in pub.status
 stats.config['enabled']=False;clock[0]=70;assert not pub.request(im,'2026-10-31T00:01:10.000Z')
print('PASS: admin-pixel exclusion at 1x/2x DPI, opt-in defaults, compressed JPEG/size bounds, 30-second throttle, GUI heartbeat during blocked network, no overlap and failure isolation')
# Exercise the actual Main capture path without an OAK or outbound request.
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
import TyreTrack_Production_Monitor as m
from test_resources import DatabaseTemporaryDirectory
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *a:True
with DatabaseTemporaryDirectory() as folder:
 m.DATA=Path(folder);m.DB=m.DATA/'test.db';m.PRIVATE_CONFIG_DIR=m.DATA/'private';m.init_db();w=m.Main();w.clock.stop();w.show();qt.processEvents()
 try:
  assert not w.web_image_enabled.isChecked()
  w._web_publisher.config=dict(schema=1,url=URL,token='test-only-'+'x'*40,enabled=True,snapshot_enabled=True)
  w._web_publisher.request=MagicMock();w._web_image_publisher.request=MagicMock()
  w.publish_dashboard_image(w.grab().toImage());assert w._web_image_publisher.request.call_count==1
  w.offline_testing=True;w.publish_dashboard_image(w.grab().toImage());assert w._web_image_publisher.request.call_count==1
 finally:w.close();qt.processEvents()
print('PASS: actual Qt dashboard capture wiring and offline test suppression; no production writes or network')
