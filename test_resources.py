"""Fixture-owned SQLite connections/cursors are explicitly closed before deletion."""
import threading
import sqlite3
import tempfile
from unittest.mock import patch

class _TestConnection(sqlite3.Connection):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._fixture_cursors=[]
        self._fixture_closed=False
        self._fixture_owner=threading.get_ident()
    def cursor(self,*args,**kwargs):
        cursor=super().cursor(*args,**kwargs)
        self._fixture_cursors.append(cursor)
        return cursor
    # sqlite3 convenience methods otherwise create cursors in C, bypassing cursor().
    def execute(self,*args,**kwargs):return self.cursor().execute(*args,**kwargs)
    def executemany(self,*args,**kwargs):return self.cursor().executemany(*args,**kwargs)
    def executescript(self,*args,**kwargs):return self.cursor().executescript(*args,**kwargs)
    def close(self):
        if self._fixture_closed:return
        for cursor in self._fixture_cursors:cursor.close()
        self._fixture_cursors.clear()
        super().close()
        self._fixture_closed=True
    def __exit__(self,*args):
        try:return super().__exit__(*args)
        finally:self.close()

class DatabaseTemporaryDirectory(tempfile.TemporaryDirectory):
    """Close owner-thread handles; detect rather than hide leaked worker handles.

    Never disables SQLite's thread checks or ignores filesystem cleanup errors.
    Callers must stop/join background workers before leaving the fixture.
    """
    def __enter__(self):
        folder=super().__enter__()
        self._connections=[];self._connection_lock=threading.Lock()
        connect=sqlite3.connect
        def tracked_connect(*args,**kwargs):
            if len(args)<6:kwargs.setdefault('factory',_TestConnection)
            connection=connect(*args,**kwargs)
            with self._connection_lock:self._connections.append((threading.get_ident(),connection))
            return connection
        self._connection_patch=patch.object(sqlite3,'connect',tracked_connect)
        self._connection_patch.start()
        return folder
    def __exit__(self,exc_type,exc_value,traceback):
        self._connection_patch.stop()
        with self._connection_lock:connections=list(self._connections)
        for owner,connection in reversed(connections):
            if owner==threading.get_ident():connection.close()
        leaked=[connection for owner,connection in connections
                if owner!=threading.get_ident() and not getattr(connection,'_fixture_closed',False)]
        self._connections.clear()
        if leaked:raise AssertionError(f'{len(leaked)} worker SQLite connection(s) still open before fixture cleanup; close in owning thread')
        return super().__exit__(exc_type,exc_value,traceback)
