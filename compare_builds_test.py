"""Check current source against contracts taken from the user's working source ZIP."""
from pathlib import Path
import ast,json,hashlib
ROOT=Path(__file__).resolve().parent
contract=json.loads((ROOT/'compatibility_baseline.json').read_text())
def digest(raw,name):
 if name.endswith('.json'):raw=json.dumps(json.loads(raw),sort_keys=True,separators=(',',':')).encode()
 elif name.endswith(('.py','.txt')):raw=raw.replace(b'\r\n',b'\n')
 return hashlib.sha256(raw).hexdigest()
tree=ast.parse((ROOT/'TyreTrack_Production_Monitor.py').read_text())
nodes={n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest() for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
problems=[]
reporting=json.loads((ROOT/'reporting_changes.json').read_text())
audited=dict(reporting['functions'])
audited.update(json.loads((ROOT/'dashboard_performance_changes.json').read_text())['functions'])
for name,change in audited.items():
 current=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
 expected=ast.parse(change['new']).body[0]
 assert ast.dump(current,include_attributes=False)==ast.dump(expected,include_attributes=False), 'Reporting change mismatch: '+name
 original=ast.parse(change['old']).body[0]
 nodes[name]=hashlib.sha256(ast.dump(original,include_attributes=False).encode()).hexdigest()
for name,sha in contract['unchanged_top_level_nodes'].items():
 if nodes.get(name)!=sha:problems.append('Changed contract: '+name)
for name,sha in contract['unchanged_files'].items():
 raw=(ROOT/name).read_bytes()
 if name=='no_count_replies.py':
  change=json.loads((ROOT/'no_count_reply_changes.json').read_text())
  assert digest(raw,name)==change['new_sha256'],'Reply module differs from audited repair'
  raw=change['old'].encode()
 if name=='oak_rvc2.py':
  change=json.loads((ROOT/'preview_pipeline_change.json').read_text())
  text=raw.decode().replace('\r\n','\n')
  assert text.count(change['new'])==1
  raw=text.replace(change['new'],change['old']).encode()
 if name=='requirements-windows.txt':
  text=raw.decode().replace('\r\n','\n');addition=reporting['requirements_added']
  assert text.endswith(addition);raw=text[:-len(addition)].encode()
 if digest(raw,name)!=sha:problems.append('Changed resource/module: '+name)
assert not problems,problems
report=dict(baseline=contract['baseline'],status='source compatibility checks passed',
 unchanged_function_or_class_contracts=len(contract['unchanged_top_level_nodes']),
 unchanged_model_module_or_dependency_files=len(contract['unchanged_files']),
 direct_video_preview_patch_validated=True,
 checks=['Audited best-day SQL aggregation replaces Python full-history scan; original semantics covered by 100k-event parity fixture','Original camera capture class unchanged; PNG encoding moved off GUI thread','Only live XLink source selected from existing camera outputs: 640x360 NV12 or original 480x270 BGR; reversing selector patch restores exact pipeline hash','Original hourly emails, alerts and count writes preserved; two audited daily/scheduler functions now produce PDF+CSV briefings','Existing Windows dependency pins preserved; ReportLab 4.4.9 added for PDFs and pypdf 6.10.0 for CI validation'],
 intentional_changes=['Independent grouped live totals; five-second historical refresh with no busy queue; fractional-position marquee on precise 33 ms timer','Branded daily and Friday weekly PDF+CSV management briefings; manual background export; HTML email','Ten replacement sounds with persisted shuffle and WAV import','Today class counts and owner-specified kg/EPU estimates','Native 640x360 live view with original-preview fallback; background PNG encoding retained','Optional sign-in shortcut installer and duplicate-instance lock','Camera stays connected outside shift; count gate remains weekday 05:00–17:05 Brisbane','Experimental shared three-line counter with adjustable top/bottom and horizontal span','OAK-only production input and separate on-screen video tester','Statistics-focused dashboard, smaller video, random no-repeat celebrations for best hour and best daily total','Additive database indexes and shift-only dashboard query'],
 physical_site_validation=False,windows_exe_built_in_this_environment=False,speaker_playback_verified=False,
 limitations=['Host-side count logic changed; counting accuracy must be compared with a hand count.','Source checks cannot guarantee camera, network, Windows DLL or speaker behavior on the yard PC.'])
(ROOT/'BUILD_COMPARISON.json').write_text(json.dumps(report,indent=2))
(ROOT/'BUILD_COMPARISON.txt').write_text('WORKING BUILD VS CURRENT BUILD\n\n'+
 '\n'.join(report['checks'])+'\n\nINTENTIONAL CHANGES\n'+ '\n'.join(report['intentional_changes'])+
 '\n\nREADINESS\nSoftware compatibility checks passed. Use a separate trial folder and preserve existing data/reports.\nBuild the Windows EXE with the included workflow. Before production, close other OAK apps, run\nRUN_OAK_HARDWARE_TEST.bat (tyre-only, 60 seconds, no production counts) and use the sound test\non the actual PC. Then hand-check counts on representative conveyor footage. Keep the old\nworking build for rollback. Camera connectivity, live accuracy and physical sound are not\nverified by these offline checks.\n',encoding='utf-8')
print('PASS: original source contracts and model/dependency integrity; direct-output selection patch verified against unchanged original pipeline hash')
