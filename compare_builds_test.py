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
for name,sha in contract['unchanged_top_level_nodes'].items():
 if nodes.get(name)!=sha:problems.append('Changed contract: '+name)
for name,sha in contract['unchanged_files'].items():
 if digest((ROOT/name).read_bytes(),name)!=sha:problems.append('Changed resource/module: '+name)
assert not problems,problems
report=dict(baseline=contract['baseline'],status='source compatibility checks passed',
 unchanged_function_or_class_contracts=len(contract['unchanged_top_level_nodes']),
 unchanged_model_module_or_dependency_files=len(contract['unchanged_files']),
 checks=['Original camera capture class unchanged','OAK pipelines, model weights and recording unchanged','Email/report and count-write functions unchanged','Windows dependency pins unchanged'],
 intentional_changes=['Camera stays connected outside shift; count gate remains weekday 05:00–17:05 Brisbane','Experimental shared three-line counter with adjustable top/bottom and horizontal span','OAK-only production input and separate on-screen video tester','Statistics-focused dashboard, smaller video, random no-repeat celebrations for best hour and best daily total','Additive database indexes and shift-only dashboard query'],
 physical_site_validation=False,windows_exe_built_in_this_environment=False,speaker_playback_verified=False,
 limitations=['Host-side count logic changed; counting accuracy must be compared with a hand count.','Source checks cannot guarantee camera, network, Windows DLL or speaker behavior on the yard PC.'])
(ROOT/'BUILD_COMPARISON.json').write_text(json.dumps(report,indent=2))
(ROOT/'BUILD_COMPARISON.txt').write_text('WORKING BUILD VS CURRENT BUILD\n\n'+
 '\n'.join(report['checks'])+'\n\nINTENTIONAL CHANGES\n'+ '\n'.join(report['intentional_changes'])+
 '\n\nREADINESS\nSoftware compatibility checks passed. Use a separate trial folder and preserve existing data/reports.\nBuild the Windows EXE with the included workflow. Before production, close other OAK apps, run\nRUN_OAK_HARDWARE_TEST.bat (tyre-only, 60 seconds, no production counts) and use the sound test\non the actual PC. Then hand-check counts on representative conveyor footage. Keep the old\nworking build for rollback. Camera connectivity, live accuracy and physical sound are not\nverified by these offline checks.\n',encoding='utf-8')
print('PASS:',report['unchanged_function_or_class_contracts'],'original source contracts and',report['unchanged_model_module_or_dependency_files'],'model/module/dependency files unchanged')
