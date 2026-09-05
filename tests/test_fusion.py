from __future__ import annotations

from claude_agent_lab.rag.fusion import rank_with_ties, reciprocal_rank_fusion


def test_rank_with_ties_orders_by_score_descending():
    ranks = rank_with_ties([("a", 1.0), ("b", 3.0), ("c", 2.0)])
    assert ranks == {"b": 1, "c": 2, "a": 3}


def test_rank_with_ties_gives_equal_scores_the_same_rank():
    # Three items tie for the top score; the next distinct score is rank 4,
    # not 2 — "competition ranking," matching how BM25 hands out identical
    # (often zero) scores to every document that doesn't contain a term.
    ranks = rank_with_ties([("a", 5.0), ("b", 5.0), ("c", 5.0), ("d", 1.0)])
    assert ranks == {"a": 1, "b": 1, "c": 1, "d": 4}


def test_rank_with_ties_handles_all_equal_scores():
    ranks = rank_with_ties([("a", 1.0), ("b", 1.0)])
    assert ranks == {"a": 1, "b": 1}


def test_reciprocal_rank_fusion_rewards_appearing_near_the_top_of_both_lists():
    # 20-candidate scenario, well clear of any rank-vs-k ambiguity: item "x"
    # is the sole rank 1 in both lists and should clearly win the fused
    # ranking over everything ranked 2nd or worse in both.
    list_a = {"x": 1, **{f"item{i}": i + 1 for i in range(1, 20)}}
    list_b = {"x": 1, **{f"item{i}": i + 1 for i in range(1, 20)}}
    fused = reciprocal_rank_fusion([list_a, list_b], k=60)
    winner = max(fused, key=lambda key: fused[key])
    assert winner == "x"


def test_reciprocal_rank_fusion_rewards_being_top_of_one_list_over_absent_from_both():
    fused = reciprocal_rank_fusion([{"a": 1}, {"a": 1, "b": 2}], k=60)
    assert fused["a"] > fused["b"]


def test_reciprocal_rank_fusion_a_small_k_makes_rank_position_matter_more():
    # Same two rankings, two different k values: a smaller k should widen
    # the gap between a rank-1 item and a rank-5 item, since 1/(k+1) grows
    # much faster than 1/(k+5) as k shrinks.
    rankings = [{"a": 1, "b": 5}]
    gap_large_k = reciprocal_rank_fusion(rankings, k=60)["a"] - reciprocal_rank_fusion(rankings, k=60)["b"]
    gap_small_k = reciprocal_rank_fusion(rankings, k=1)["a"] - reciprocal_rank_fusion(rankings, k=1)["b"]
    assert gap_small_k > gap_large_k


def test_reciprocal_rank_fusion_on_no_rankings_returns_empty():
    assert reciprocal_rank_fusion([], k=60) == {}


def test_reciprocal_rank_fusion_item_missing_from_a_list_gets_no_credit_from_it():
    # "only_in_a" appears solely in the first ranking; its fused score
    # should equal exactly that single list's contribution.
    fused = reciprocal_rank_fusion([{"only_in_a": 1}, {"other": 1}], k=60)
    assert fused["only_in_a"] == 1.0 / 61
