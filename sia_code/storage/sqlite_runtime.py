"""SQLite runtime helpers with FTS5 compatibility checks."""

from pathlib import Path
import sqlite3 as stdlib_sqlite3


def _supports_fts5(sqlite_module) -> bool:
    """Return True when the given sqlite module supports FTS5."""
    conn = sqlite_module.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE fts_probe USING fts5(content)")
        conn.execute("DROP TABLE fts_probe")
        return True
    except sqlite_module.OperationalError:
        return False
    finally:
        conn.close()


def _resolve_sqlite_module():
    """Resolve a sqlite module with working FTS5 support."""
    if _supports_fts5(stdlib_sqlite3):
        return stdlib_sqlite3

    try:
        import pysqlite3 as pysqlite3  # type: ignore
    except Exception as exc:
        try:
            from pysqlite3 import dbapi2 as pysqlite3  # type: ignore
        except Exception:
            raise RuntimeError(
                "SQLite FTS5 is not available in this Python runtime. "
                "Install a Python build with FTS5 enabled or install pysqlite3-binary."
            ) from exc

    if _supports_fts5(pysqlite3):
        return pysqlite3

    raise RuntimeError(
        "No SQLite runtime with FTS5 support is available. "
        "Install sqlite with FTS5 enabled or install pysqlite3-binary."
    )


_SQLITE_MODULE = None


def get_sqlite_module():
    """Return a cached sqlite module with FTS5 support."""
    global _SQLITE_MODULE
    if _SQLITE_MODULE is None:
        _SQLITE_MODULE = _resolve_sqlite_module()
    return _SQLITE_MODULE


def connect_sqlite(path: Path, check_same_thread: bool = False):
    """Create a sqlite connection with row factory configured."""
    sqlite_module = get_sqlite_module()
    conn = sqlite_module.connect(str(path), check_same_thread=check_same_thread)
    conn.row_factory = sqlite_module.Row
    return conn
