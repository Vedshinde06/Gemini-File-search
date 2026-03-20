import os
import time
from gemini_client import client

STORE_DISPLAY_NAME = os.getenv("FILE_SEARCH_STORE_NAME")
_cached_store = None


def get_or_create_store():
    global _cached_store

    if _cached_store is not None:
        return _cached_store

    for store in client.file_search_stores.list():
        if STORE_DISPLAY_NAME in store.display_name:
            _cached_store = store
            return store

    _cached_store = client.file_search_stores.create(
        config={"display_name": STORE_DISPLAY_NAME}
    )
    return _cached_store


def upload_file_to_store(file_path: str):
    file_name = os.path.basename(file_path)

    store = get_or_create_store()

    operation = client.file_search_stores.upload_to_file_search_store(
        file=file_path,
        file_search_store_name=store.name,
        config={
            "display_name": file_name,
            "chunking_config": {
                "white_space_config": {
                    "max_tokens_per_chunk": 220,
                    "max_overlap_tokens": 30
                }
            }
        }
    )

    while not operation.done:
        time.sleep(2)
        operation = client.operations.get(operation)

    return {"status": "indexed", "file": file_name}
