import sqlite3
import unittest

from src.db.schema import MIGRATIONS, get_schema_version, initialize_schema, migrate_schema


class SchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        initialize_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_creates_core_tables(self) -> None:
        tables = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }

        self.assertEqual(
            tables,
            {
                "stocks",
                "prices",
                "fundamentals",
                "scores",
                "risk_flags",
                "rankings",
                "pipeline_runs",
                "schema_migrations",
            },
        )

    def test_creates_expected_indexes(self) -> None:
        indexes = {
            row[0]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'"
            )
        }

        self.assertEqual(
            indexes,
            {
                "idx_prices_code_date",
                "idx_fundamentals_code_year",
                "idx_scores_run_date",
                "idx_rankings_run_date_rank",
                "idx_risk_flags_code_date",
                "idx_rankings_market",
                "idx_rankings_sector",
                "idx_stocks_market",
            },
        )

    def test_enables_foreign_keys_and_sets_schema_version(self) -> None:
        foreign_keys = self.conn.execute("PRAGMA foreign_keys").fetchone()[0]
        user_version = self.conn.execute("PRAGMA user_version").fetchone()[0]

        self.assertEqual(foreign_keys, 1)
        self.assertEqual(user_version, 1)
        self.assertEqual(get_schema_version(self.conn), 1)

    def test_rejects_invalid_market_and_status_values(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO stocks (stock_code, stock_name, market) VALUES (?, ?, ?)",
                ("000001", "invalid", "NYSE"),
            )

        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO pipeline_runs (run_date, status) VALUES (?, ?)",
                ("2026-05-20", "DONE"),
            )

    def test_records_schema_version_in_migration_table(self) -> None:
        versions = [
            row[0]
            for row in self.conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]

        self.assertEqual(versions, [1])

    def test_migrate_schema_initializes_blank_database(self) -> None:
        conn = sqlite3.connect(":memory:")
        try:
            migrate_schema(conn)

            self.assertEqual(get_schema_version(conn), 1)
            table_count = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'stocks'"
            ).fetchone()[0]
            self.assertEqual(table_count, 1)
        finally:
            conn.close()

    def test_migrate_schema_applies_forward_migration(self) -> None:
        MIGRATIONS[2] = "CREATE TABLE IF NOT EXISTS migration_test (id INTEGER PRIMARY KEY);"
        try:
            migrate_schema(self.conn, target_version=2)

            self.assertEqual(get_schema_version(self.conn), 2)
            table_count = self.conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'migration_test'"
            ).fetchone()[0]
            versions = [
                row[0]
                for row in self.conn.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            ]
            self.assertEqual(table_count, 1)
            self.assertEqual(versions, [1, 2])
        finally:
            MIGRATIONS.pop(2, None)

    def test_migrate_schema_rejects_missing_forward_migration(self) -> None:
        with self.assertRaises(RuntimeError):
            migrate_schema(self.conn, target_version=2)


if __name__ == "__main__":
    unittest.main()
