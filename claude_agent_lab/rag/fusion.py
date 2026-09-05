"""Reciprocal Rank Fusion (RRF): combine several ranked lists into one.

`HybridRetriever` uses this to merge a semantic-similarity ranking and a
BM25 keyword ranking into a single fused ranking — without needing the two
lists' raw scores to be on comparable scales (cosine similarity and a BM25
score are not the same kind of number). RRF only looks at each item's
*rank* within each list, never its score's magnitude.
"""

from __future__ import annotations


def rank_with_ties(scored_items: list[tuple[str, float]]) -> dict[str, int]:
    """Rank items by score, descending, using competition ranking: items
    tied on score share the same rank (1, 2, 2, 4 — not 1, 2, 3, 4).

    This matters for BM25 specifically: most documents in a small corpus
    won't contain a given query term at all and tie at the same (possibly
    zero) score. Handing them arbitrary sequential ranks (2, 3, 4, 5...)
    based on nothing but iteration order would quietly give whichever one
    lands rank 2 an undeserved edge once fused — as if it were meaningfully
    more relevant than the others it's actually tied with.
    """
    ranks: dict[str, int] = {}
    previous_score: float | None = None
    current_rank = 0
    for position, (key, score) in enumerate(
        sorted(scored_items, key=lambda item: item[1], reverse=True), start=1
    ):
        if score != previous_score:
            current_rank = position
            previous_score = score
        ranks[key] = current_rank
    return ranks


def reciprocal_rank_fusion(rankings: list[dict[str, int]], *, k: int = 60) -> dict[str, float]:
    """Combine several rank-only signals into one fused score per key.

    `fused(key) = sum(1 / (k + rank))` over every ranking that contains that
    key; missing from a ranking contributes nothing from that one.

    `k=60` is the standard constant from Cormack, Clarke & Buettcher (2009),
    tuned for large-scale search where result lists run into the dozens or
    hundreds. At a much smaller scale — a handful to a few dozen candidates,
    which is this project's realistic corpus size for a while — the gap
    between rank 1 and rank N is tiny relative to `k`, so RRF barely
    distinguishes ranks and a single-list rank-1 item can outscore an item
    that's rank-1 in the *other* list but last in this one. Pass a smaller
    `k` to make rank position matter more at small scale; see
    docs/progress.md for the worked example that surfaced this.
    """
    fused: dict[str, float] = {}
    for ranking in rankings:
        for key, rank in ranking.items():
            fused[key] = fused.get(key, 0.0) + 1.0 / (k + rank)
    return fused
