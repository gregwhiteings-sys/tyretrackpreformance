"""Persistent FOD startup choice and the requested one-time default-on upgrade."""
import sqlite3

MIGRATION_KEY = 'fod_default_on_v1'

def foreign_enabled_at_startup(database):
    """Enable on first launch of this update, then respect the saved choice."""
    with sqlite3.connect(database, timeout=15) as con:
        con.execute('BEGIN IMMEDIATE')
        migrated = con.execute('SELECT value FROM state WHERE key=?', (MIGRATION_KEY,)).fetchone()
        if migrated is None:
            con.execute("INSERT OR REPLACE INTO state(key,value) VALUES('foreign_enabled','1')")
            con.execute('INSERT INTO state(key,value) VALUES(?,?)', (MIGRATION_KEY, '1'))
            return True
        saved = con.execute("SELECT value FROM state WHERE key='foreign_enabled'").fetchone()
        return saved is None or saved[0] != '0'
