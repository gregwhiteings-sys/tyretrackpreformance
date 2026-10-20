"""Temporary test directories that explicitly release SQLite handles on Windows."""
import threading
import sqlite3
import tempfile
from unittest.mock import patch

class _TestConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

class DatabaseTemporaryDirectory(tempfile.TemporaryDirectory):
    """Own connections opened within a test fixture, including exceptional exits.

    SQLite's transaction context manager commits/rolls back but does not close.
    Keep production behavior intact; release fixture resources before deletion.
    """
    def __enter__(self):
        folder = super().__enter__()
        self._connections = []
        connect = sqlite3.connect
        owner_thread = threading.get_ident()
        def tracked_connect(*args, **kwargs):
            if len(args) < 6:
                kwargs.setdefault('factory', _TestConnection)
            connection = connect(*args, **kwargs)
            if threading.get_ident() == owner_thread:
                self._connections.append(connection)
            return connection
        self._connection_patch = patch.object(sqlite3, 'connect', tracked_connect)
        self._connection_patch.start()
        return folder

    def __exit__(self, exc_type, exc_value, traceback):
        self._connection_patch.stop()
        try:
            for connection in reversed(self._connections):
                connection.close()
            self._connections.clear()
        finally:
            super().__exit__(exc_type, exc_value, traceback)
