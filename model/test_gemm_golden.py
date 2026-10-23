import numpy as np
from gemm_golden import gemm_int8, make_vectors


def test_most_negative():
    A = np.full((4, 4), -128, np.int8)
    B = np.full((4, 4), -128, np.int8)
    # each product is 16384, summed over K=4 -> 65536
    assert (gemm_int8(A, B) == 65536).all()


def test_most_positive():
    A = np.full((4, 4), 127, np.int8)
    B = np.full((4, 4), 127, np.int8)
    # each product is 16129, summed over K=4 -> 64516
    assert (gemm_int8(A, B) == 64516).all()


def test_mixed_sign():
    A = np.full((4, 4), -128, np.int8)
    B = np.full((4, 4), 127, np.int8)
    # each product is -16256, summed over K=4 -> -65024
    assert (gemm_int8(A, B) == -65024).all()


def test_identity():
    A = np.arange(16, dtype=np.int8).reshape(4, 4)
    I = np.eye(4, dtype=np.int8)
    assert (gemm_int8(A, I) == A.astype(np.int32)).all()


def test_vectors_match_numpy():
    for A, B, C in make_vectors(n_random=200):
        assert C.dtype == np.int32
        assert (C == A.astype(np.int64) @ B.astype(np.int64)).all()
