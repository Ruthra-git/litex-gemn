import json
import numpy as np


def gemm_int8(A, B):
    """int8 x int8 -> int32 matrix multiply (the bit-exact reference)."""
    assert A.dtype == np.int8 and B.dtype == np.int8
    assert A.shape[1] == B.shape[0]
    return A.astype(np.int32) @ B.astype(np.int32)


def make_vectors(n_random=1000, m=4, k=4, n=4, seed=0):
    rng = np.random.default_rng(seed)
    lo, hi = -128, 127
    cases = [
        (np.full((m, k), lo, np.int8), np.full((k, n), lo, np.int8)),  # most negative
        (np.full((m, k), hi, np.int8), np.full((k, n), hi, np.int8)),  # most positive
        (np.full((m, k), lo, np.int8), np.full((k, n), hi, np.int8)),  # mixed sign
        (np.zeros((m, k), np.int8), np.zeros((k, n), np.int8)),        # zeros
    ]
    for _ in range(n_random):
        cases.append((rng.integers(lo, hi + 1, (m, k), dtype=np.int8),
                      rng.integers(lo, hi + 1, (k, n), dtype=np.int8)))
    return [(A, B, gemm_int8(A, B)) for A, B in cases]


def dump_vectors(path, **kwargs):
    vecs = make_vectors(**kwargs)
    out = [{"A": A.tolist(), "B": B.tolist(), "C": C.tolist()} for A, B, C in vecs]
    with open(path, "w") as f:
        json.dump(out, f)
    return len(out)


if __name__ == "__main__":
    n = dump_vectors("tb/vectors_4x4.json")
    print(f"wrote {n} vectors to tb/vectors_4x4.json")
