from google.cloud import firestore
import time

db = firestore.Client()
_links_cache = None
_links_cache_at = 0
_LINKS_CACHE_TTL_SECONDS = 300

def save_doc(name, drive_url):
    global _links_cache, _links_cache_at

    db.collection("documents").document(name).set({
        "drive_url": drive_url
    })
    if _links_cache is None:
        _links_cache = {}
    _links_cache[name] = drive_url
    _links_cache_at = time.time()

def get_all_links(force_refresh: bool = False):
    global _links_cache, _links_cache_at

    if (
        not force_refresh
        and _links_cache is not None
        and (time.time() - _links_cache_at) < _LINKS_CACHE_TTL_SECONDS
    ):
        return _links_cache

    docs = db.collection("documents").stream()
    mapping = {}

    for doc in docs:
        data = doc.to_dict()
        mapping[doc.id] = data.get("drive_url")

    _links_cache = mapping
    _links_cache_at = time.time()
    return mapping
