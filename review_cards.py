"""Compact operator readings; display only, no counting or classification writes."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame,QHBoxLayout,QVBoxLayout,QLabel,QPushButton,QSizePolicy

class ReviewCards(QFrame):
    def __init__(self,review_callback,enabled=True,parent=None):
        super().__init__(parent)
        self.setObjectName('reviewReadings')
        self.enabled=bool(enabled)
        row=QHBoxLayout(self);row.setContentsMargins(0,0,0,0);row.setSpacing(8)
        self.cards=[]
        for name,title,accent in [('overlapAdditionsCard','TODAY · OVERLAP +1','#57e5ca'),('observeOnlyCard','TODAY · OBSERVE-ONLY','#74caff')]:
            card=QFrame();card.setObjectName(name);card.setFixedHeight(168)
            card.setMinimumWidth(0);card.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
            card.setStyleSheet(f'QFrame#{name} {{background:#14232b;border:1px solid #45616d;border-radius:6px;}} QLabel {{border:0;background:transparent;color:#c9e5ef;}}')
            layout=QVBoxLayout(card);layout.setContentsMargins(10,8,10,8);layout.setSpacing(3)
            label=QLabel(title);label.setStyleSheet(f'font:700 12px "Segoe UI";color:{accent};');layout.addWidget(label)
            row.addWidget(card,1);self.cards.append(card)
        left=self.cards[0].layout()
        self.additions=QLabel('—');self.additions.setStyleSheet('font:800 42px "Segoe UI";color:#57e5ca;');left.addWidget(self.additions)
        self.included=QLabel('Already included in production total');self.included.setStyleSheet('font:11px "Segoe UI";');left.addWidget(self.included)
        self.status=QLabel();self.status.setStyleSheet('font:600 11px "Segoe UI";');left.addWidget(self.status)
        left.addStretch(1)
        self.review_button=QPushButton('Open overlap count reviews');self.review_button.setFixedHeight(25)
        self.review_button.setStyleSheet('font:600 11px "Segoe UI";padding:2px;')
        self.review_button.clicked.connect(review_callback);left.addWidget(self.review_button)
        right=self.cards[1].layout();self.values={}
        for key,name in [('passenger','Passenger'),('4x4','SUV / 4×4'),('truck','Truck'),('unknown','Unclassified')]:
            line=QHBoxLayout();line.setContentsMargins(0,0,0,0)
            label=QLabel(name);label.setStyleSheet('font:600 12px "Segoe UI";')
            value=QLabel('—');value.setAlignment(Qt.AlignRight|Qt.AlignVCenter);value.setStyleSheet('font:700 19px "Segoe UI";color:#74caff;')
            line.addWidget(label,1);line.addWidget(value,1);right.addLayout(line);self.values[key]=value
        right.addStretch(1)
        note=QLabel('Not used for production totals');note.setStyleSheet('font:11px "Segoe UI";');right.addWidget(note)
        self.set_enabled(enabled)

    def set_enabled(self,enabled):
        self.enabled=bool(enabled)
        self.status.setText('On · 65% confidence' if self.enabled else 'Off · no automatic additions')
        self.status.setToolTip('Existing overlap counting conditions and confidence are unchanged.')

    def show_result(self,result):
        if 'error' in result:
            self.additions.setText('—')
            for value in self.values.values():value.setText('—')
            self.included.setText('Readings unavailable')
            self.setToolTip(str(result['error']));return
        self.setToolTip('');self.included.setText('Already included in production total')
        self.additions.setText('+'+format(int(result.get('automatic_overlap_added',0)),','))
        counts=result.get('assisted_counts',{})
        for key,value in self.values.items():
            n=int(counts.get(key,0))+(int(counts.get('uncertain_or_unmeasured',0)) if key=='unknown' else 0)
            value.setText(format(n,','))

    def show_status(self,text):
        # Keep actionable faults visible; detailed diagnostics remain in tooltip/log.
        upper=text.upper();self.status.setToolTip(text)
        if 'NOT SAVED' in upper:self.status.setText('Save failed · review required')
        elif 'OFF:' in upper or 'ERROR' in upper:self.status.setText('Fault · automatic additions unavailable')
        elif self.enabled:self.status.setText('On · 65% confidence')
        else:self.status.setText('Off · no automatic additions')
