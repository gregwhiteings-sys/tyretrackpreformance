"""Display the overlap experiment's evidence without activating a failed model.
No inference, count writes, camera streams or alarm calls are made here.
"""
import json
from pathlib import Path

def read_status(folder):
    try:
        report=json.loads((Path(folder)/'trial_status.json').read_text(encoding='utf-8'))
        stats=report['held_out_test']
        return dict(status='BLOCKED',title='OVERLAP AI MODEL · OFF · FAILED VALIDATION',
                    detail=f"Held-out test: {stats['tp']} matched groups / {stats['tp']+stats['fn']} labelled; "
                           f"false detections on {stats['false_positive_images']} / {stats['negative_images']} normal frames.",
                    report=report)
    except (OSError,ValueError,KeyError,TypeError):
        return dict(status='BLOCKED',title='OVERLAP AI MODEL · OFF · RESULTS UNAVAILABLE',
                    detail='Model evidence unavailable. Original counting continues.',report={})

def dashboard_panel(parent,folder):
    from PyQt5.QtWidgets import QFrame,QVBoxLayout,QLabel,QPushButton,QMessageBox
    state=read_status(folder)
    panel=QFrame(parent);panel.setObjectName('overlapTrialPanel')
    panel.setStyleSheet('#overlapTrialPanel {background:#29251c;border:1px solid #a68a43;border-radius:6px;}')
    layout=QVBoxLayout(panel);layout.setContentsMargins(8,6,8,6);layout.setSpacing(4)
    title=QLabel(state['title']);title.setStyleSheet('color:#f1c568;font:700 12px "Segoe UI";')
    detail=QLabel(state['detail']);detail.setWordWrap(True);detail.setStyleSheet('color:#efdfb8;font:11px "Segoe UI";')
    button=QPushButton('Overlap trial results / count verification')
    def explain():
        QMessageBox.information(parent,'Overlap trial — not approved for live use',
            state['detail']+'\n\nThis candidate did not pass validation. It is stored for inspection only; no additional '
            'camera inference, foreign alarms or production counts are enabled.\n\n'
            'To verify whether overlapped tyres were counted, review the timestamped clip alongside the recorded '
            'tyre tracks and actual count events. An overlap box cannot tell us how many hidden tyres are present. '
            'The separate geometric review links observed tyre IDs to actual count events; it does not run this failed model or prove how many hidden tyres exist.\n\n'
            'Next step: collect and annotate more independent overlap events, retrain and evaluate fresh footage.')
    button.clicked.connect(explain)
    layout.addWidget(title);layout.addWidget(detail);layout.addWidget(button)
    return panel
