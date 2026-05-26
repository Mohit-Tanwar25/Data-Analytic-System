"""
Dataset storage API — all data is persisted in MySQL via database.py.
"""

from io import BytesIO

import pandas as pd

from analysis import clean_data
from database import (
    count_duplicate_datasets,
    deduplicate_datasets_by_name,
    delete_dataset,
    run_dataset_cleanup,
    format_uploaded_at,
    get_active_dataset_id,
    get_dataset,
    init_database_tables,
    list_datasets,
    load_dataset_from_database,
    load_from_database,
    save_dataset_to_database,
    set_active_dataset,
    storage_stats,
)

__all__ = [
    "count_duplicate_datasets",
    "deduplicate_datasets_by_name",
    "run_dataset_cleanup",
    "delete_dataset",
    "format_uploaded_at",
    "get_active_dataset_id",
    "get_dataset",
    "get_dataset_path",
    "init_database_tables",
    "list_datasets",
    "load_dataset_from_database",
    "load_from_database",
    "set_active_dataset",
    "storage_stats",
    "store_uploaded_csv",
]


def get_dataset_path(dataset_id: str):
    """Data lives in MySQL; returns dataset_id if it exists."""
    if get_dataset(dataset_id):
        return dataset_id
    return None


def store_uploaded_csv(file_bytes: bytes, original_name: str) -> str | None:
    df = pd.read_csv(BytesIO(file_bytes))
    df = clean_data(df)
    return save_dataset_to_database(df, original_name, file_bytes)
