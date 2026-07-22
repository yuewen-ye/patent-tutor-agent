"""Lazy MySQL connection pooling and versioned schema migrations."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, LifoQueue
import re
import threading
from typing import Any, Iterator
from urllib.parse import unquote, urlparse


class MySQLConfigurationError(RuntimeError):
    """Raised when the MySQL driver or connection configuration is unavailable."""


@dataclass(frozen=True, slots=True)
class MySQLSettings:
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "patent_tutor"
    charset: str = "utf8mb4"
    connect_timeout: int = 5

    @classmethod
    def from_url(cls, url: str | None) -> "MySQLSettings":
        if not url:
            return cls()
        parsed = urlparse(url)
        if parsed.scheme not in {"mysql", "mysql+pymysql"}:
            raise MySQLConfigurationError(
                "PATENT_TUTOR_MYSQL_URL must use mysql:// or mysql+pymysql://."
            )
        if not parsed.hostname:
            raise MySQLConfigurationError("MySQL URL must include a host.")
        defaults = cls()
        database = parsed.path.lstrip("/") or defaults.database
        if not re.fullmatch(r"[A-Za-z0-9_]+", database):
            raise MySQLConfigurationError("MySQL database name contains invalid characters.")
        return cls(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=unquote(parsed.username or defaults.user),
            password=unquote(parsed.password or ""),
            database=database,
        )


class MySQLDatabase:
    """Small DB-API pool with lazy driver import and idempotent migrations.

    The application can be imported without a running MySQL server. The first
    repository operation opens the pool and applies migrations, which keeps
    unit tests and CLI module discovery deterministic.
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        pool_size: int = 5,
        connect_timeout: int = 5,
        migrations_dir: str | Path | None = None,
        auto_migrate: bool = True,
    ) -> None:
        if pool_size < 1:
            raise ValueError("pool_size must be positive")
        settings = MySQLSettings.from_url(url)
        self.settings = MySQLSettings(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            password=settings.password,
            database=settings.database,
            charset=settings.charset,
            connect_timeout=connect_timeout,
        )
        self.pool_size = pool_size
        self.auto_migrate = auto_migrate
        self.migrations_dir = Path(migrations_dir) if migrations_dir else Path(__file__).parent / "migrations"
        self._pool: LifoQueue[Any] = LifoQueue(maxsize=pool_size)
        self._created = 0
        self._pool_lock = threading.Lock()
        self._initialize_lock = threading.Lock()
        self._initialized = False

    def _driver(self) -> Any:
        try:
            import pymysql  # type: ignore[import-untyped]
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on environment
            raise MySQLConfigurationError(
                "PyMySQL is required for MySQL persistence. Run `uv sync`."
            ) from exc
        return pymysql

    def _connect(self, *, with_database: bool = True) -> Any:
        driver = self._driver()
        kwargs: dict[str, Any] = {
            "host": self.settings.host,
            "port": self.settings.port,
            "user": self.settings.user,
            "password": self.settings.password,
            "charset": self.settings.charset,
            "connect_timeout": self.settings.connect_timeout,
            "autocommit": False,
            "cursorclass": driver.cursors.DictCursor,
        }
        if with_database:
            kwargs["database"] = self.settings.database
        return driver.connect(**kwargs)

    def ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self._initialize_lock:
            if self._initialized:
                return
            admin = self._connect(with_database=False)
            try:
                database = self.settings.database.replace("`", "``")
                with admin.cursor() as cursor:
                    cursor.execute(
                        f"CREATE DATABASE IF NOT EXISTS `{database}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                    )
                admin.commit()
            finally:
                admin.close()

            connection = self._connect(with_database=True)
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "CREATE TABLE IF NOT EXISTS schema_migrations ("
                        "version VARCHAR(64) PRIMARY KEY, "
                        "applied_at DATETIME(6) NOT NULL) ENGINE=InnoDB"
                    )
                    for migration in sorted(self.migrations_dir.glob("*.sql")):
                        version = migration.stem
                        cursor.execute(
                            "SELECT 1 FROM schema_migrations WHERE version=%s LIMIT 1",
                            (version,),
                        )
                        if cursor.fetchone():
                            continue
                        for statement in _split_sql(migration.read_text(encoding="utf-8")):
                            cursor.execute(statement)
                        cursor.execute(
                            "INSERT INTO schema_migrations(version, applied_at) "
                            "VALUES (%s, UTC_TIMESTAMP(6))",
                            (version,),
                        )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
            self._initialized = True

    def expected_migrations(self) -> list[str]:
        return [migration.stem for migration in sorted(self.migrations_dir.glob("*.sql"))]

    def applied_migrations(self) -> list[str]:
        connection = self._connect(with_database=True)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
                return [str(row["version"]) for row in cursor.fetchall()]
        finally:
            connection.close()

    def pending_migrations(self) -> list[str]:
        applied = set(self.applied_migrations())
        return [version for version in self.expected_migrations() if version not in applied]

    def unexpected_migrations(self) -> list[str]:
        expected = set(self.expected_migrations())
        return [version for version in self.applied_migrations() if version not in expected]

    def _connect_tracked(self) -> Any:
        try:
            return self._connect()
        except Exception:
            with self._pool_lock:
                self._created = max(0, self._created - 1)
            raise

    def _acquire(self) -> Any:
        try:
            connection = self._pool.get_nowait()
        except Empty:
            create_new = False
            with self._pool_lock:
                if self._created < self.pool_size:
                    self._created += 1
                    create_new = True
            if create_new:
                return self._connect_tracked()
            connection = self._pool.get()
        try:
            connection.ping()
        except Exception:
            try:
                connection.close()
            except Exception:
                pass
            with self._pool_lock:
                self._created = max(0, self._created - 1)
                self._created += 1
            return self._connect_tracked()
        return connection

    def _release(self, connection: Any) -> None:
        try:
            self._pool.put_nowait(connection)
        except Exception:
            try:
                connection.close()
            finally:
                with self._pool_lock:
                    self._created = max(0, self._created - 1)

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        if self.auto_migrate:
            self.ensure_initialized()
        connection = self._acquire()
        try:
            connection.begin()
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            self._release(connection)

    def close(self) -> None:
        while True:
            try:
                connection = self._pool.get_nowait()
            except Empty:
                break
            connection.close()
            with self._pool_lock:
                self._created = max(0, self._created - 1)
        self._initialized = False


def _split_sql(script: str) -> list[str]:
    """Split migration SQL; migration files intentionally avoid procedural SQL."""

    statements: list[str] = []
    for raw in script.split(";"):
        lines = [line for line in raw.splitlines() if not line.strip().startswith("--")]
        statement = "\n".join(lines).strip()
        if statement:
            statements.append(statement)
    return statements
