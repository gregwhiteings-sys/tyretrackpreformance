"""Native Qt truck instruments. Presentation layer only; no counting or I/O."""
import math,re
from PyQt5.QtCore import Qt,QRectF,QPointF
from PyQt5.QtGui import QPainter,QPixmap,QColor,QPen,QFont,QLinearGradient,QRadialGradient,QPolygonF
from PyQt5.QtWidgets import QWidget,QFrame,QLabel,QVBoxLayout,QHBoxLayout,QGridLayout,QPushButton,QProgressBar,QDialog,QSizePolicy


def numeric(label):
    match=re.search(r'[\d,]+',label.text())
    return int(match.group().replace(',','')) if match else 0


class MetalPanel(QWidget):
    def __init__(self,path,parent=None):
        super().__init__(parent)
        self.texture=QPixmap(str(path))
        self._surface=QPixmap()
    def resizeEvent(self,event):
        self._surface=QPixmap(self.size());self._surface.fill(QColor('#11161b'))
        p=QPainter(self._surface)
        if not self.texture.isNull():p.drawPixmap(self.rect(),self.texture)
        p.fillRect(self.rect(),QColor(2,8,12,105));p.end()
        super().resizeEvent(event)
    def paintEvent(self,event):
        p=QPainter(self)
        if not self._surface.isNull():p.drawPixmap(0,0,self._surface)


class Instrument(QWidget):
    def __init__(self,mode,parent=None):
        super().__init__(parent)
        self.mode=mode;self.rate=0.;self.current=0;self.best=0;self.flash=False
        self._dial=QPixmap();self.static_renders=0
        self.setMinimumSize(210,225)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.setAccessibleName('Tyres per minute' if mode=='flow' else 'Best completed production hour')
    def resizeEvent(self,event):
        self._dial=QPixmap(self.size());self._dial.fill(Qt.transparent)
        p=QPainter(self._dial);self._prepare(p);self._base(p);p.end();self.static_renders+=1
        super().resizeEvent(event)
    def _prepare(self,p):
        p.setRenderHint(QPainter.Antialiasing)
        side=min(self.width(),self.height());p.translate(self.width()/2,self.height()/2);p.scale(side/320,side/320)
    @staticmethod
    def _point(value,r):
        a=math.radians(225-270*value)
        return QPointF(math.cos(a)*r,-math.sin(a)*r)
    @staticmethod
    def _text(p,rect,value,size,colour,bold=True):
        p.setPen(QColor(colour));font=QFont('Segoe UI');font.setPixelSize(size);font.setBold(bold);p.setFont(font);p.drawText(QRectF(*rect),Qt.AlignCenter,value)
    def _base(self,p):
        ring=QLinearGradient(-150,-150,150,150)
        ring.setColorAt(0,QColor('#a6b0b7'));ring.setColorAt(.17,QColor('#151b21'));ring.setColorAt(.48,QColor('#4b555e'));ring.setColorAt(.7,QColor('#080c10'));ring.setColorAt(1,QColor('#86939a'))
        p.setPen(QPen(QColor('#020608'),3));p.setBrush(ring);p.drawEllipse(QRectF(-154,-154,308,308))
        p.setPen(QPen(QColor('#61727e'),1));p.setBrush(QColor('#03090e'));p.drawEllipse(QRectF(-144,-144,288,288))
        face=QRadialGradient(0,-35,160);face.setColorAt(0,QColor('#14232e'));face.setColorAt(1,QColor('#03080c'))
        p.setPen(QPen(QColor('#192c37'),2));p.setBrush(face);p.drawEllipse(QRectF(-138,-138,276,276))
        colour='#45c6ff' if self.mode=='flow' else '#53f894'
        for i in range(51):
            f=i/50;outer=self._point(f,130);inner=self._point(f,116 if i%5==0 else 122)
            p.setPen(QPen(QColor(colour if i%5==0 else '#28526a'),2.5 if i%5==0 else 1));p.drawLine(inner,outer)
        if self.mode=='flow':
            for i in range(11):
                point=self._point(i/10,100)
                self._text(p,(point.x()-16,point.y()-11,32,22),str(i*2),14,'#d9edf7')
            self._text(p,(-80,-64,160,30),'FLOW',19,'#a6dfff')
        else:self._text(p,(-104,-74,208,30),'BEST HOUR',19,'#c6ecdc')
    def set_values(self,rate,current,best,flash=False):
        values=(rate,current,best,flash)
        if values==(self.rate,self.current,self.best,self.flash):return
        self.rate,self.current,self.best,self.flash=values
        self.update()
    def paintEvent(self,event):
        p=QPainter(self)
        if not self._dial.isNull():p.drawPixmap(0,0,self._dial)
        self._prepare(p)
        if self.mode=='flow':
            f=max(0,min(1,self.rate/20));tip=self._point(f,112);tail=self._point(f,-16)
            p.setPen(QPen(QColor('#7de5ff'),4,Qt.SolidLine,Qt.RoundCap));p.drawLine(tail,tip)
            p.setBrush(QColor('#c4efff'));p.setPen(QPen(QColor('#34556a'),3));p.drawEllipse(QPointF(0,0),9,9)
            self._text(p,(-96,43,192,53),f'{self.rate:.1f}',46,'#ff6570' if self.flash else '#42c7ff')
            self._text(p,(-120,97,240,23),'TYRES / MIN',14,'#b4cedd')
            if self.rate>20:self._text(p,(-110,121,220,15),'ABOVE DIAL RANGE',9,'#8eb4c7')
        else:
            fraction=min(1,max(0,self.current/self.best)) if self.best else 0
            p.setPen(QPen(QColor('#15352b'),14,Qt.SolidLine,Qt.FlatCap));p.drawArc(QRectF(-130,-130,260,260),-45*16,270*16)
            if fraction:
                for i in range(round(fraction*45)):
                    a=self._point(i/45,123);b=self._point(i/45,135)
                    p.setPen(QPen(QColor('#55fb93'),6));p.drawLine(a,b)
            self._text(p,(-118,-25,236,64),f'{self.best:,}',49,'#edfaff')
            self._text(p,(-100,40,200,24),'tyres',17,'#b7d1da')
            self._text(p,(-130,85,260,23),f'{self.current:,} / {self.best:,}' if self.best else 'FIRST HOUR IN PROGRESS',14,'#62d4ff')
            self._text(p,(-90,110,180,28),f'{int(fraction*100)}%' if self.best else '—',24,'#50d0ff')


def install(main,resource):
    """Reuse existing data labels, video widget and controls; retain old admin pages."""
    legacy=main.takeCentralWidget();legacy.setParent(main);legacy.hide();main._legacy_dashboard=legacy
    texture=resource('truck_metal.png')
    root=MetalPanel(texture);root.setObjectName('truckRoot');main.setCentralWidget(root)
    outer=QVBoxLayout(root);outer.setContentsMargins(12,8,12,8);outer.setSpacing(6)
    header=QHBoxLayout()
    brand=QLabel('TYRE<span style="color:#46c9f4">TRACK</span>');brand.setStyleSheet("font:900 italic 27px 'Segoe UI';color:#eef6fa;background:transparent;")
    header.addWidget(brand)
    logo=QLabel();logo.setObjectName('truckOfficialLogo')
    logo_path=texture.with_name('tyrecycle_logo.png')
    pixmap=QPixmap(str(logo_path))
    if not pixmap.isNull():
        logo.setPixmap(pixmap.scaled(150,48,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        logo.setToolTip('Tyrecycle • A ResourceCo Company')
        header.addWidget(logo)
    subtitle=QLabel('TYRECYCLE  •  PRODUCTION MONITOR');subtitle.setStyleSheet('color:#9db3c1;font-size:12px;letter-spacing:1px;background:transparent;');header.addWidget(subtitle);header.addStretch()
    header.addWidget(main.health)
    main.truck_clock=QLabel();main.truck_clock.setStyleSheet("font:700 18px 'Consolas';color:#eef7ff;background:transparent;");header.addWidget(main.truck_clock)
    outer.addLayout(header)
    outer.addWidget(main.alarm_banner)
    cluster=QHBoxLayout();cluster.setSpacing(10)
    main.flow_instrument=Instrument('flow');cluster.addWidget(main.flow_instrument,3)
    centre=QFrame();centre.setObjectName('truckCentre');centre.setMinimumWidth(350)
    centre.setStyleSheet('#truckCentre {background:#030b11;border:2px solid #526b78;border-radius:12px;}')
    c=QVBoxLayout(centre);c.setContentsMargins(14,10,14,10);c.setSpacing(3)
    title=QLabel('THIS HOUR');title.setObjectName('metricName');title.setAlignment(Qt.AlignCenter);title.setStyleSheet('font-size:23px;font-weight:900;color:#c8dce7;background:transparent;');c.addWidget(title)
    main.hour_lbl.setAlignment(Qt.AlignCenter);main.hour_lbl.setStyleSheet("font:900 82px 'Consolas';color:#edfaff;background:transparent;");c.addWidget(main.hour_lbl,1)
    main.record_progress.setFixedHeight(44);main.record_progress.setStyleSheet("font:800 20px 'Segoe UI';color:#55f1d7;");c.addWidget(main.record_progress)
    main.hour_target_bar=QProgressBar();main.hour_target_bar.setRange(0,1000);main.hour_target_bar.setFixedHeight(20);main.hour_target_bar.setFormat('%p%');c.addWidget(main.hour_target_bar)
    main.current_hour_card=centre;cluster.addWidget(centre,4)
    main.best_instrument=Instrument('best');cluster.addWidget(main.best_instrument,3)
    outer.addLayout(cluster,4)
    middle=QHBoxLayout();middle.setSpacing(8)
    def tile(name,label,colour):
        card=QFrame();card.setObjectName('truckTile');card.setStyleSheet('#truckTile {background:#071117;border:1px solid #465964;border-radius:9px;}');box=QVBoxLayout(card);box.setContentsMargins(10,9,10,8);box.setSpacing(3)
        title=QLabel(name);title.setStyleSheet('color:#b2c7d2;font-size:13px;font-weight:800;background:transparent;');title.setAlignment(Qt.AlignCenter);box.addWidget(title)
        label.setAlignment(Qt.AlignCenter);label.setWordWrap(False);label.setMinimumWidth(0);label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Expanding)
        label.setStyleSheet("color:"+colour+";font:900 38px 'Consolas';background:transparent;");box.addWidget(label,1)
        unit=QLabel('tyres');unit.setAlignment(Qt.AlignCenter);unit.setStyleSheet('font-size:15px;color:#bad0da;background:transparent;');box.addWidget(unit)
        return card
    # Today already includes an HTML units suffix; use only one visible unit label.
    main.truck_best_day_value=QLabel('0')
    for name,label,colour in [('TODAY',main.day_lbl,'#effaff'),('BEST DAY',main.truck_best_day_value,'#effaff'),('PASSENGER',main.passenger_lbl,'#4bf28e'),('SUV / 4×4',main.suv_lbl,'#40bfff')]:
        card=tile(name,label,colour)
        if name=='TODAY':
            card.layout().itemAt(2).widget().hide()
            if name=='BEST DAY':label.setWordWrap(True);label.setStyleSheet("font:900 23px 'Consolas';color:#effaff;background:transparent;")
        middle.addWidget(card,2)
    main.camera_panel=QFrame();main.camera_panel.setObjectName('truckCamera')
    camera=QVBoxLayout(main.camera_panel);camera.setContentsMargins(4,3,4,3);camera.setSpacing(2)
    camera.addWidget(main.test_transport);camera.addWidget(main.test_progress)
    main.video.setMinimumSize(220,112);camera.addWidget(main.video,1)
    main._truck_camera_layout=camera;middle.addWidget(main.camera_panel,4)
    outer.addLayout(middle,2)
    secondary=QHBoxLayout();secondary.setSpacing(10)
    for title,label in [('AVERAGES',main.production_average),('ALL TIME',main.total_lbl),('NO-COUNT ALERTS',main.no_count_lbl),('SHIFT',main.production_status_lbl)]:
        box=QFrame();box.setObjectName('truckMini');layout=QHBoxLayout(box);layout.setContentsMargins(8,3,8,3)
        title=QLabel(title);title.setStyleSheet('font-size:10px;font-weight:800;color:#8ba5b5;background:transparent;');layout.addWidget(title)
        label.setMinimumWidth(0);label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);label.setWordWrap(True);label.setStyleSheet("font:700 13px 'Segoe UI';color:#c1d8e4;background:transparent;");layout.addWidget(label,1);secondary.addWidget(box,1)
    outer.addLayout(secondary)
    main.hourly_strip.setFixedHeight(78)
    for label in main.dashboard_hour_blocks:label.setFixedHeight(54)
    outer.addWidget(main.hourly_strip)
    footer=QHBoxLayout();footer.setSpacing(6)
    admin=next(x for x in legacy.findChildren(QPushButton) if x.text()=='Admin Settings')
    upload=next(x for x in legacy.findChildren(QPushButton) if x.text()=='Upload video test')
    for widget in (main.start_btn,main.stop_btn,admin,upload,main.edit_bounds_btn):footer.addWidget(widget)
    full=QPushButton('Fullscreen');full.clicked.connect(main.open_fullscreen);footer.addWidget(full)
    footer.addStretch();footer.addWidget(main.celebration_indicator);outer.addLayout(footer)
    main.status_lbl.setStyleSheet('font-size:10px;color:#91acba;background:transparent;');outer.addWidget(main.status_lbl)
    outer.addWidget(main.celebration_banner)
    main.truck_admin_dialog=QDialog(main);main.truck_admin_dialog.setWindowTitle('TyreTrack • Admin settings')
    admin_layout=QVBoxLayout(main.truck_admin_dialog);admin_layout.addWidget(main.controls_tabs)
    main.controls_tabs.setMinimumWidth(0);main.controls_tabs.setMaximumWidth(16777215)
    main.controls_tabs.show()
    def admin_toggle():
        if main.truck_admin_dialog.isVisible():main.truck_admin_dialog.hide();return
        if main._confirm_admin_pin('open settings'):
            main.controls_tabs.show();bounds=main.screen().availableGeometry();main.truck_admin_dialog.resize(min(1000,bounds.width()-60),min(720,bounds.height()-80));main.truck_admin_dialog.show();main.truck_admin_dialog.raise_()
    admin.clicked.disconnect();admin.clicked.connect(admin_toggle)
    main.truck_admin_dialog.finished.connect(lambda _:main.controls_tabs.hide())
    main._truck_show_admin=admin_toggle
    # Edit the real video in a large window, retaining all existing drag signals.
    main.truck_line_dialog=QDialog(main);main.truck_line_dialog.setWindowTitle('TyreTrack • Align conveyor lines')
    line_layout=QVBoxLayout(main.truck_line_dialog)
    lock=QPushButton('Lock lines and return');lock.clicked.connect(lambda:main.edit_bounds_btn.setChecked(False))
    line_layout.addWidget(lock)
    def edit_lines(enabled):
        if enabled:
            line_layout.insertWidget(0,main.video,1);bounds=main.screen().availableGeometry();main.truck_line_dialog.resize(min(1050,bounds.width()-60),min(700,bounds.height()-80));main.truck_line_dialog.show()
        else:
            camera.addWidget(main.video,1);main.truck_line_dialog.hide()
    main.edit_bounds_btn.toggled.connect(edit_lines)
    main.truck_line_dialog.finished.connect(lambda _:main.edit_bounds_btn.setChecked(False))
    main.setStyleSheet(main.styleSheet()+"""
      #truckRoot QWidget {background:transparent;}
      #truckCentre,#truckTile,#truckMini,#truckCamera {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0c1922,stop:1 #03080c);border:1px solid #52636d;border-radius:10px;}
      #truckCentre {border:2px solid #5c747e;}
      QProgressBar {background:#02090d;border:1px solid #496873;border-radius:8px;text-align:center;color:#d9ffed;font-size:11px;font-weight:800;}
      QProgressBar::chunk {background:#4bf28e;border-radius:7px;}
      QDialog {background:#07111c;}
      #truckRoot QPushButton {padding:5px 10px;font-size:11px;}
    """)
    main.setWindowTitle('TyreTrack • Truck Dashboard Trial')
    main.truck_dashboard_ready=True
    sync(main)


def sync(main):
    if not getattr(main,'truck_dashboard_ready',False):return
    try:rate=float(main.flow_lbl.text())
    except ValueError:rate=0.
    current=numeric(main.hour_lbl);best=numeric(main.session_lbl)
    for label in (main.passenger_lbl,main.suv_lbl):
        value=numeric(label)
        if label.text()!=f'{value:,}':label.setText(f'{value:,}')
    main.truck_best_day_value.setText(f'{numeric(main.best_daily_lbl):,}')
    main.truck_best_day_value.setToolTip(main.best_daily_lbl.toolTip())
    size=min(144,max(84,round(main.current_hour_card.height()*.32)))
    if getattr(main,'_truck_number_size',None)!=size:
        main._truck_number_size=size
        main.hour_lbl.setStyleSheet(f"font:900 {size}px 'Consolas';color:#edfaff;background:transparent;")
    main.flow_instrument.set_values(rate,current,best,getattr(main,'_flow_flash_red',False))
    main.best_instrument.set_values(rate,current,best)
    main.hour_target_bar.setValue(round(min(1,current/best)*1000) if best else 0)
    main.hour_target_bar.setToolTip(f'{current:,} of {best:,} tyres; {max(0,best+1-current):,} to set a new record' if best else 'Waiting for the first completed hour')
    from hourly_dashboard import brisbane_now
    main.truck_clock.setText('Brisbane  '+brisbane_now().strftime('%H:%M'))
