import numpy as np

from domain_guard.scorer import PrototypeScorer, scaled_cosine


def test_integer_cosine_is_exact_and_stable():
    left = np.asarray([100, 0], dtype=np.int16)
    same = np.asarray([50, 0], dtype=np.int16)
    opposite = np.asarray([-50, 0], dtype=np.int16)
    assert scaled_cosine(left, same, 10000) == 10000
    assert scaled_cosine(left, opposite, 10000) == -10000


def test_prototype_scorer_uses_closest_examples():
    positive = np.asarray([[100, 0], [0, 100]], dtype=np.int16)
    negative = np.asarray([[-100, 0]], dtype=np.int16)
    score = PrototypeScorer(positive, negative, 10000).score(
        np.asarray([[90, 10]], dtype=np.int16)
    )[0]
    assert score.in_score > 9000
    assert score.out_score < 0
    assert score.margin > score.in_score
