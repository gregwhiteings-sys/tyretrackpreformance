"""The actual reply-integrity guard accepts LF/CRLF but rejects code changes."""
import ast,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
source=ast.parse((ROOT/'compare_builds_test.py').read_text())
digest=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='digest')
loop=next(n for n in source.body if isinstance(n,ast.For) and ast.unparse(n.iter)=="contract['unchanged_files'].items()")
guard=next(n for n in loop.body if isinstance(n,ast.If) and ast.unparse(n.test)=="name == 'no_count_replies.py'")
code=compile(ast.Module(body=[digest,guard],type_ignores=[]),'<actual-integrity-guard>','exec')
raw=(ROOT/'no_count_replies.py').read_bytes().replace(b'\r\n',b'\n')
baseline=json.loads((ROOT/'compatibility_baseline.json').read_text())['unchanged_files']['no_count_replies.py']
for newline in (b'\n',b'\r\n'):
 ns=dict(hashlib=hashlib,json=json,ROOT=ROOT,name='no_count_replies.py',raw=raw.replace(b'\n',newline))
 exec(code,ns)
 assert ns['digest'](ns['raw'],'no_count_replies.py')==baseline
for value in (raw.replace(b'saved=0',b'saved=1'),raw.replace(b'saved=0',b'saved=1').replace(b'\n',b'\r\n')):
 assert value!=raw
 try:exec(code,dict(hashlib=hashlib,json=json,ROOT=ROOT,name='no_count_replies.py',raw=value))
 except AssertionError as exc:assert 'Reply module differs' in str(exc)
 else:raise AssertionError('Changed code incorrectly accepted')
print('PASS: actual audited guard accepts LF/CRLF, restores baseline, rejects modified code under both newline styles')
