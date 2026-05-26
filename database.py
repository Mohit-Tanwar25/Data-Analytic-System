import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ---------------- DATABASE CONFIG ----------------

DB_USER = "root"
DB_PASSWORD = "25022005"
DB_HOST = "localhost"
DB_NAME = "analysis"

DATASETS_TABLE = "datasets"
RECORDS_TABLE = "sales_records"

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

STANDARD_COLUMNS = [
    "order_id",
    "order_date",
    "ship_date",
    "category",
    "product_name",
    "region",
    "sales",
    "profit",
    "quantity",
    "discount",
    "shipping_cost",
]


def table_exists(table_name: str) -> bool:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = :schema
                    AND table_name = :table
                    """
                ),
                {"schema": DB_NAME, "table": table_name},
            )
            return bool(result.scalar())
    except Exception:
        return False


def init_database_tables() -> bool:
    """Create datasets and sales_records tables if they do not exist."""
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {DATASETS_TABLE} (
                        id VARCHAR(12) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        uploaded_at DATETIME NOT NULL,
                        row_count INT DEFAULT 0,
                        column_count INT DEFAULT 0,
                        content_hash VARCHAR(32),
                        is_active TINYINT(1) DEFAULT 0,
                        INDEX idx_dataset_name (name)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {RECORDS_TABLE} (
                        record_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        dataset_id VARCHAR(12) NOT NULL,
                        order_id VARCHAR(100),
                        order_date DATE,
                        ship_date DATE,
                        category VARCHAR(100),
                        product_name VARCHAR(255),
                        region VARCHAR(100),
                        sales DOUBLE,
                        profit DOUBLE,
                        quantity INT,
                        discount DOUBLE,
                        shipping_cost FLOAT,
                        CONSTRAINT fk_sales_dataset
                            FOREIGN KEY (dataset_id)
                            REFERENCES {DATASETS_TABLE}(id)
                            ON DELETE CASCADE,
                        INDEX idx_dataset_id (dataset_id)
                    )
                    """
                )
            )
            _drop_unique_name_constraint(connection)
        return True
    except SQLAlchemyError as e:
        print("Database Init Error:")
        print(e)
        return False


def _drop_unique_name_constraint(connection) -> None:
    """Allow many datasets (including same filename uploaded multiple times)."""
    try:
        connection.execute(
            text(
                f"""
                ALTER TABLE {DATASETS_TABLE}
                DROP INDEX uq_dataset_name
                """
            )
        )
    except Exception:
        pass


def count_datasets() -> int:
    return len(list_datasets())


def _file_hash(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in STANDARD_COLUMNS:
        if col not in out.columns:
            out[col] = None
    out = out[STANDARD_COLUMNS]
    out.insert(0, "dataset_id", None)
    return out


def _normalize_dataset_record(item: dict) -> dict:
    item["is_active"] = bool(item.get("is_active"))
    item["rows"] = int(item.get("row_count") or item.get("rows") or 0)
    item["columns"] = int(item.get("column_count") or item.get("columns") or 0)
    if hasattr(item.get("uploaded_at"), "isoformat"):
        item["uploaded_at"] = item["uploaded_at"].isoformat()
    else:
        item["uploaded_at"] = str(item.get("uploaded_at", ""))
    return item


def find_dataset_by_name(name: str) -> dict | None:
    init_database_tables()
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    f"""
                    SELECT id, name, uploaded_at, row_count, column_count,
                           content_hash, is_active
                    FROM {DATASETS_TABLE}
                    WHERE LOWER(name) = LOWER(:name)
                    LIMIT 1
                    """
                ),
                {"name": name.strip()},
            ).mappings().first()
        if not row:
            return None
        item = dict(row)
        _normalize_dataset_record(item)
        return item
    except SQLAlchemyError as e:
        print("Find Dataset Error:")
        print(e)
        return None


def list_datasets() -> list[dict]:
    init_database_tables()
    try:
        df = pd.read_sql(
            f"""
            SELECT id, name, uploaded_at, row_count, column_count,
                   content_hash, is_active
            FROM {DATASETS_TABLE}
            ORDER BY uploaded_at DESC
            """,
            con=engine,
        )
        records = df.to_dict(orient="records")
        for item in records:
            _normalize_dataset_record(item)
        return records
    except SQLAlchemyError as e:
        print("List Datasets Error:")
        print(e)
        return []


def get_dataset(dataset_id: str) -> dict | None:
    init_database_tables()
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    f"""
                    SELECT id, name, uploaded_at, row_count, column_count,
                           content_hash, is_active
                    FROM {DATASETS_TABLE}
                    WHERE id = :id
                    """
                ),
                {"id": dataset_id},
            ).mappings().first()
        if not row:
            return None
        item = dict(row)
        _normalize_dataset_record(item)
        return item
    except SQLAlchemyError as e:
        print("Get Dataset Error:")
        print(e)
        return None


def get_active_dataset_id() -> str | None:
    init_database_tables()
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    f"""
                    SELECT id FROM {DATASETS_TABLE}
                    WHERE is_active = 1
                    LIMIT 1
                    """
                ),
            ).first()
        return row[0] if row else None
    except SQLAlchemyError:
        return None


def set_active_dataset(dataset_id: str | None) -> None:
    init_database_tables()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(f"UPDATE {DATASETS_TABLE} SET is_active = 0")
            )
            if dataset_id:
                connection.execute(
                    text(
                        f"""
                        UPDATE {DATASETS_TABLE}
                        SET is_active = 1
                        WHERE id = :id
                        """
                    ),
                    {"id": dataset_id},
                )
    except SQLAlchemyError as e:
        print("Set Active Dataset Error:")
        print(e)


def _storage_label(original_name: str) -> str:
    """Keep original filename; uploads with the same name are separate datasets."""
    return original_name.strip()


def save_dataset_to_database(
    df: pd.DataFrame,
    original_name: str,
    file_bytes: bytes | None = None,
    *,
    replace_existing_name: bool = False,
) -> str | None:
    """Save dataset rows in MySQL. Each upload creates a new dataset by default."""
    init_database_tables()

    original_name = original_name.strip()
    content_hash = _file_hash(file_bytes) if file_bytes else ""
    storage_name = _storage_label(original_name)
    uploaded_at = datetime.now(timezone.utc).replace(tzinfo=None)

    row_count = int(df.shape[0])
    column_count = int(df.shape[1])

    existing = find_dataset_by_name(storage_name) if replace_existing_name else None
    dataset_id = existing["id"] if existing else uuid4().hex[:12]

    if df.empty:
        print("Save Dataset Error: dataframe is empty after cleaning")
        return None

    try:
        with engine.begin() as connection:
            if existing and replace_existing_name:
                connection.execute(
                    text(f"DELETE FROM {RECORDS_TABLE} WHERE dataset_id = :id"),
                    {"id": dataset_id},
                )
                connection.execute(
                    text(
                        f"""
                        UPDATE {DATASETS_TABLE}
                        SET uploaded_at = :uploaded_at,
                            row_count = :row_count,
                            column_count = :column_count,
                            content_hash = :content_hash
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": dataset_id,
                        "uploaded_at": uploaded_at,
                        "row_count": row_count,
                        "column_count": column_count,
                        "content_hash": content_hash,
                    },
                )
            else:
                connection.execute(
                    text(
                        f"""
                        INSERT INTO {DATASETS_TABLE}
                            (id, name, uploaded_at, row_count, column_count,
                             content_hash, is_active)
                        VALUES
                            (:id, :name, :uploaded_at, :row_count, :column_count,
                             :content_hash, 0)
                        """
                    ),
                    {
                        "id": dataset_id,
                        "name": storage_name,
                        "uploaded_at": uploaded_at,
                        "row_count": row_count,
                        "column_count": column_count,
                        "content_hash": content_hash,
                    },
                )

            records_df = _normalize_dataframe(df)
            records_df["dataset_id"] = dataset_id
            records_df.to_sql(
                name=RECORDS_TABLE,
                con=connection,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=500,
            )

        return dataset_id

    except (SQLAlchemyError, pd.errors.DatabaseError, Exception) as e:
        print("Save Dataset Error:")
        print(e)
        return None


def load_dataset_from_database(dataset_id: str) -> pd.DataFrame:
    init_database_tables()
    if not table_exists(RECORDS_TABLE):
        return pd.DataFrame()

    try:
        df = pd.read_sql(
            text(
                f"""
                SELECT order_id, order_date, ship_date, category, product_name,
                       region, sales, profit, quantity, discount, shipping_cost
                FROM {RECORDS_TABLE}
                WHERE dataset_id = :dataset_id
                """
            ),
            con=engine,
            params={"dataset_id": dataset_id},
        )
        return df
    except (SQLAlchemyError, pd.errors.DatabaseError, Exception) as e:
        print("Load Dataset Error:")
        print(e)
        return pd.DataFrame()


def load_from_database() -> pd.DataFrame:
    """Load rows for the currently active dataset."""
    active_id = get_active_dataset_id()
    if not active_id:
        return pd.DataFrame()
    return load_dataset_from_database(active_id)


def save_to_database(df: pd.DataFrame) -> bool:
    """Backward-compatible: save active dataset rows (requires active id)."""
    active_id = get_active_dataset_id()
    if not active_id:
        return False

    dataset = get_dataset(active_id)
    if not dataset:
        return False

    result = save_dataset_to_database(df, dataset["name"])
    return result is not None


def delete_dataset(dataset_id: str) -> bool:
    init_database_tables()
    try:
        with engine.begin() as connection:
            connection.execute(
                text(f"DELETE FROM {DATASETS_TABLE} WHERE id = :id"),
                {"id": dataset_id},
            )
        return True
    except SQLAlchemyError as e:
        print("Delete Dataset Error:")
        print(e)
        return False


def clear_active_dataset_rows() -> bool:
    active_id = get_active_dataset_id()
    if not active_id:
        return True
    try:
        with engine.begin() as connection:
            connection.execute(
                text(f"DELETE FROM {RECORDS_TABLE} WHERE dataset_id = :id"),
                {"id": active_id},
            )
        set_active_dataset(None)
        return True
    except SQLAlchemyError as e:
        print("Clear Active Dataset Error:")
        print(e)
        return False


def clear_database() -> bool:
    """Clear active dataset only (legacy name)."""
    return clear_active_dataset_rows()


def _parse_uploaded_at_value(value) -> datetime:
    """Parse DB/API timestamps; naive values are treated as UTC (how we store them)."""
    if isinstance(value, datetime):
        dt = value
    else:
        text_value = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text_value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_uploaded_at(item: dict) -> datetime:
    try:
        return _parse_uploaded_at_value(item.get("uploaded_at")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return datetime.min


def _duplicate_ids_to_remove(datasets: list[dict]) -> tuple[set[str], dict[str, int]]:
    """Newest upload wins per filename and per identical file content (hash)."""
    by_name: set[str] = set()
    by_hash: set[str] = set()
    sorted_newest_first = sorted(
        datasets,
        key=_parse_uploaded_at,
        reverse=True,
    )

    seen_names: set[str] = set()
    for item in sorted_newest_first:
        name_key = item["name"].strip().lower()
        if name_key in seen_names:
            by_name.add(item["id"])
        else:
            seen_names.add(name_key)

    seen_hashes: set[str] = set()
    for item in sorted_newest_first:
        content_hash = (item.get("content_hash") or "").strip()
        if not content_hash:
            continue
        if content_hash in seen_hashes:
            by_hash.add(item["id"])
        else:
            seen_hashes.add(content_hash)

    return by_name | by_hash, {
        "by_name": len(by_name),
        "by_hash": len(by_hash),
    }


def count_duplicate_datasets() -> dict:
    """How many datasets would be removed by cleanup (preview, no deletes)."""
    init_database_tables()
    datasets = list_datasets()
    remove_ids, breakdown = _duplicate_ids_to_remove(datasets)
    return {
        "total": len(remove_ids),
        "by_name": breakdown["by_name"],
        "by_hash": breakdown["by_hash"],
        "remaining_after": len(datasets) - len(remove_ids),
    }


def run_dataset_cleanup() -> dict:
    """
    Remove duplicate saved datasets (keeps newest per filename and per file hash).
    Returns summary for UI feedback.
    """
    init_database_tables()
    datasets = list_datasets()
    if not datasets:
        return {
            "removed": 0,
            "remaining": 0,
            "by_name": 0,
            "by_hash": 0,
            "cleared_active": False,
        }

    remove_ids, breakdown = _duplicate_ids_to_remove(datasets)
    if not remove_ids:
        return {
            "removed": 0,
            "remaining": len(datasets),
            "by_name": 0,
            "by_hash": 0,
            "cleared_active": False,
        }

    active_id = get_active_dataset_id()
    removed = 0
    for dataset_id in remove_ids:
        if delete_dataset(dataset_id):
            removed += 1

    cleared_active = bool(active_id and active_id in remove_ids)
    if cleared_active:
        set_active_dataset(None)

    remaining = len(list_datasets())
    return {
        "removed": removed,
        "remaining": remaining,
        "by_name": breakdown["by_name"],
        "by_hash": breakdown["by_hash"],
        "cleared_active": cleared_active,
    }


def deduplicate_datasets_by_name() -> int:
    """Backward-compatible wrapper."""
    return run_dataset_cleanup()["removed"]


def storage_stats() -> dict:
    datasets = list_datasets()
    total_rows = sum(int(d.get("row_count", 0) or 0) for d in datasets)
    return {
        "count": len(datasets),
        "total_rows": total_rows,
        "total_size_mb": 0,
    }


def format_uploaded_at(iso_value: str) -> str:
    """Show upload time in the user's local timezone."""
    try:
        local_dt = _parse_uploaded_at_value(iso_value).astimezone()
        return local_dt.strftime("%b %d, %Y %I:%M %p")
    except (TypeError, ValueError):
        return str(iso_value)


def test_database_connection() -> bool:
    try:
        with engine.connect():
            return True
    except SQLAlchemyError as e:
        print("Database Connection Failed:")
        print(e)
        return False


__all__ = [
    "clear_active_dataset_rows",
    "clear_database",
    "count_duplicate_datasets",
    "deduplicate_datasets_by_name",
    "run_dataset_cleanup",
    "delete_dataset",
    "find_dataset_by_name",
    "format_uploaded_at",
    "get_active_dataset_id",
    "get_dataset",
    "init_database_tables",
    "list_datasets",
    "load_dataset_from_database",
    "load_from_database",
    "save_dataset_to_database",
    "save_to_database",
    "set_active_dataset",
    "storage_stats",
    "test_database_connection",
]
