"""search.py - Retrieval: HR searches candidates in plain English.
Semantic search (MiniLM + Chroma, built fresh from the DB each time) with a keyword fallback.
"""
import re

_EF = None


def keyword_search(conn, query, k=5):
    terms = [t for t in re.findall(r"[a-z0-9+#.]+", query.lower()) if len(t) > 1]
    results = []
    for app_id, name, status, text in conn.execute(
            "SELECT application_id, name, status, resume_text FROM applications WHERE resume_text IS NOT NULL"):
        low = text.lower()
        hits = [t for t in terms if t in low]
        if hits:
            results.append({"application_id": app_id, "name": name, "status": status,
                            "score": round(len(hits) / len(terms), 2), "matched": ", ".join(hits)})
    return sorted(results, key=lambda r: -r["score"])[:k]


def semantic_search(conn, query, k=5):
    import chromadb
    from chromadb.utils import embedding_functions
    rows = conn.execute("SELECT application_id, name, status, resume_text FROM applications "
                        "WHERE resume_text IS NOT NULL").fetchall()
    if not rows:
        return []
    global _EF
    if _EF is None:                                           # load MiniLM once
        _EF = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    col = chromadb.EphemeralClient().get_or_create_collection(
        "resumes", embedding_function=_EF, metadata={"hnsw:space": "cosine"})
    col.upsert(ids=[r[0] for r in rows], documents=[r[3] for r in rows],
               metadatas=[{"name": r[1] or "", "status": r[2] or ""} for r in rows])
    res = col.query(query_texts=[query], n_results=min(k, len(rows)))
    return [{"application_id": i, "name": m["name"], "status": m["status"],
             "score": round(1 - d, 2), "matched": "semantic"}              # cosine similarity, higher = closer
            for i, m, d in zip(res["ids"][0], res["metadatas"][0], res["distances"][0])]


def search(conn, query, k=5):
    """Returns (results, method). Falls back to keyword search if Chroma/model is unavailable."""
    try:
        return semantic_search(conn, query, k), "semantic (MiniLM + Chroma)"
    except Exception as e:
        print(f"[search] semantic failed ({type(e).__name__}), using keyword search")
        return keyword_search(conn, query, k), "keyword"
