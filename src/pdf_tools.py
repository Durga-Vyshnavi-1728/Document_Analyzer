
"""Hybrid keyword and semantic document search."""

import math
import re
from collections import Counter

STOP = set("""
a an the and for are was were this that with from what when where which who how why
does did can could would should about into your you their there have has had not but
its our they them then than also such these those will is it of to in on by as be or
""".split())

ALIASES = {
    "owner": {
        "owner", "policyholder", "proposer", "holder",
        "insured", "customer", "account holder"
    },
    "tenure": {
        "tenure", "duration", "period", "term",
        "validity", "expiry", "commencement"
    },
    "cost": {
        "cost", "premium", "fee", "amount", "price",
        "payment", "stipend", "salary", "compensation"
    },
    "package": {
        "package", "stipend", "salary", "compensation",
        "benefits", "remuneration", "perks"
    },
    "deadline": {
        "deadline", "due date", "last date",
        "acceptance", "return", "submit", "sign"
    },
    "coverage": {
        "coverage", "cover", "benefit",
        "protection", "insured", "claim"
    }
}


def terms(text):
    words = re.findall(
        r"[a-zA-Z0-9][a-zA-Z0-9'-]{1,}",
        text.lower()
    )
    return [word for word in words if word not in STOP]


def expanded_query(question):
    query = set(terms(question))

    for key, values in ALIASES.items():
        alias_terms = set(terms(" ".join(values)))

        if key in query or query.intersection(alias_terms):
            query.update(alias_terms)

    return query


def keyword_scores(question, chunks):
    query = expanded_query(question)

    if not query or not chunks:
        return [0.0] * len(chunks)

    documents = [terms(chunk["text"]) for chunk in chunks]
    document_frequency = Counter(
        term for document in documents for term in set(document)
    )

    total = len(documents)
    scores = []

    for document in documents:
        counts = Counter(document)
        score = 0.0

        for term in query:
            frequency = counts.get(term, 0)

            if frequency:
                idf = math.log(
                    1 + (
                        total - document_frequency[term] + 0.5
                    ) / (document_frequency[term] + 0.5)
                )

                score += idf * (
                    frequency * 2.2
                ) / (frequency + 1.2)

        scores.append(score)

    return scores


def cosine_similarity(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if not norm_a or not norm_b:
        return 0.0

    return dot / (norm_a * norm_b)


def find_relevant_chunks(
    question,
    chunks,
    limit=8,
    query_embedding=None,
    chunk_embeddings=None
):
    if not chunks:
        return []

    lexical = keyword_scores(question, chunks)

    lexical_order = sorted(
        range(len(chunks)),
        key=lambda i: lexical[i],
        reverse=True
    )

    has_semantic = (
        query_embedding is not None
        and chunk_embeddings is not None
        and len(chunk_embeddings) == len(chunks)
    )

    if has_semantic:
        semantic = [
            cosine_similarity(query_embedding, vector)
            for vector in chunk_embeddings
        ]

        semantic_order = sorted(
            range(len(chunks)),
            key=lambda i: semantic[i],
            reverse=True
        )

        lexical_rank = {
            index: rank for rank, index in enumerate(lexical_order)
        }

        semantic_rank = {
            index: rank for rank, index in enumerate(semantic_order)
        }

        ranked = sorted(
            range(len(chunks)),
            key=lambda i: (
                1 / (60 + lexical_rank[i])
                + 1 / (60 + semantic_rank[i])
            ),
            reverse=True
        )

        candidates = [
            i for i in ranked
            if lexical[i] > 0 or semantic[i] >= 0.30
        ]

    else:
        candidates = [
            i for i in lexical_order if lexical[i] > 0
        ]

    if not candidates:
        return []

    selected = []
    seen = set()

    for index in candidates:
        chunk = chunks[index]

        identity = (
            chunk.get("source"),
            chunk.get("location"),
            chunk.get("page")
        )

        if identity in seen and len(selected) >= max(3, limit // 2):
            continue

        selected.append(chunk)
        seen.add(identity)

        if len(selected) >= limit:
            break

    return selected
