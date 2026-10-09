"""Durable deletion requests, safe across separate file-sharing processes."""
from pathlib import Path
import sqlite3


def database():
    directory = Path.home() / 'MagicC'
    directory.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(directory / 'share-cleanup.sqlite3', timeout=10)
    connection.execute('CREATE TABLE IF NOT EXISTS pending (account TEXT, fileid INTEGER, PRIMARY KEY (account, fileid))')
    return connection


def enqueue(account, fileid):
    connection = database()
    try:
        with connection:
            connection.execute('INSERT OR IGNORE INTO pending VALUES (?, ?)', (account, fileid))
    finally:
        connection.close()


def pending(account):
    connection = database()
    try:
        return [row[0] for row in connection.execute('SELECT fileid FROM pending WHERE account = ?', (account,))]
    finally:
        connection.close()


def complete(account, fileid):
    connection = database()
    try:
        with connection:
            connection.execute('DELETE FROM pending WHERE account = ? AND fileid = ?', (account, fileid))
    finally:
        connection.close()
