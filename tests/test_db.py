import pytest

import app.db as db_module


class FakeConnection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakePool:
    def __init__(self, connection):
        self.connection = connection
        self.returned = []

    def getconn(self):
        return self.connection

    def putconn(self, connection, close=False):
        self.returned.append((connection, close))


def test_commits_and_returns_database_connection(monkeypatch):
    connection = FakeConnection()
    pool = FakePool(connection)
    monkeypatch.setattr(db_module, "get_connection_pool", lambda: pool)

    with db_module.get_db_connection() as acquired:
        assert acquired is connection

    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert pool.returned == [(connection, False)]


def test_rolls_back_and_returns_failed_database_connection(monkeypatch):
    connection = FakeConnection()
    pool = FakePool(connection)
    monkeypatch.setattr(db_module, "get_connection_pool", lambda: pool)

    with pytest.raises(RuntimeError, match="query failed"):
        with db_module.get_db_connection():
            raise RuntimeError("query failed")

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert pool.returned == [(connection, False)]


def test_discards_closed_database_connection(monkeypatch):
    connection = FakeConnection()
    connection.closed = 1
    pool = FakePool(connection)
    monkeypatch.setattr(db_module, "get_connection_pool", lambda: pool)

    with db_module.get_db_connection():
        pass

    assert pool.returned == [(connection, True)]
