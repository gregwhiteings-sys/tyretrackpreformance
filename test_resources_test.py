"""Fixture connection/cursor lifecycle must be deterministic, including worker threads."""
import sqlite3,threading
from pathlib import Path
from test_resources import DatabaseTemporaryDirectory

with DatabaseTemporaryDirectory() as folder:
 db=Path(folder)/'handles.db';held=[]
 def work():
  with sqlite3.connect(db) as con:
   con.execute('CREATE TABLE data(value INTEGER)')
   con.executemany('INSERT INTO data VALUES(?)',[(1,),(2,),(3,)])
   cursor=con.execute('SELECT * FROM data');assert cursor.fetchone()==(1,)
   held.extend([con,cursor]) # Retain Python references beyond the worker lifetime.
 thread=threading.Thread(target=work);thread.start();thread.join(3);assert not thread.is_alive()
 assert held[0]._fixture_closed and not held[0]._fixture_cursors
 try:held[1].fetchone();raise AssertionError('Cursor survived explicit connection cleanup')
 except sqlite3.ProgrammingError:pass
 moved=db.with_suffix('.moved');db.rename(moved);moved.rename(db)
assert not Path(folder).exists()

# A live worker leak is reported explicitly instead of hidden by rmtree errors.
fixture=DatabaseTemporaryDirectory();folder=fixture.__enter__();release=threading.Event();opened=threading.Event()
def leaking_worker():
 con=sqlite3.connect(Path(folder)/'leak.db');opened.set();release.wait(3);con.close()
thread=threading.Thread(target=leaking_worker);thread.start();assert opened.wait(1)
try:
 try:fixture.__exit__(None,None,None);raise AssertionError('Open worker connection was not detected')
 except AssertionError as exc:assert 'worker SQLite connection' in str(exc)
finally:
 release.set();thread.join(3);assert not thread.is_alive();fixture.cleanup()
assert not Path(folder).exists()
print('PASS retained worker connection/unread cursor explicitly closed, rename/delete after worker exit, open worker leak detected without ignoring cleanup errors')
