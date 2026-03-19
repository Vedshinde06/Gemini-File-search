from google.cloud import firestore

db = firestore.Client()

def save_doc(name, drive_url):
    db.collection("documents").document(name).set({
        "drive_url": drive_url
    })

def get_all_links():
    docs = db.collection("documents").stream()
    mapping = {}

    for doc in docs:
        data = doc.to_dict()
        mapping[doc.id] = data.get("drive_url")

    return mapping