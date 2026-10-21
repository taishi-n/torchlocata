"""Independent rectangular minimum-cost assignment, without third-party code."""

import numpy as np
from numpy.typing import NDArray


def minimum_assignment(
    cost: NDArray[np.float64],
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Assign every row of the smaller dimension using shortest augmenting paths.

    Finite costs only; ascending column scans give deterministic ties. This is
    an independent implementation, not a port of LOCATA's bundled solvers.
    """
    if cost.ndim != 2 or not np.isfinite(cost).all():
        raise ValueError("assignment costs must be a finite matrix")
    transpose = cost.shape[0] > cost.shape[1]
    matrix = cost.T if transpose else cost
    rows, cols = matrix.shape
    if not rows:
        empty = np.empty(0, dtype=np.int64)
        return empty, empty.copy()
    row_potential = np.zeros(rows + 1)
    col_potential = np.zeros(cols + 1)
    owner = np.zeros(cols + 1, dtype=np.int64)
    previous = np.zeros(cols + 1, dtype=np.int64)
    for row in range(1, rows + 1):
        owner[0] = row
        slack = np.full(cols + 1, np.inf)
        used = np.zeros(cols + 1, dtype=bool)
        column = 0
        while True:
            used[column] = True
            current = owner[column]
            step, next_column = np.inf, 0
            for candidate in range(1, cols + 1):
                if used[candidate]:
                    continue
                reduced = (
                    matrix[current - 1, candidate - 1]
                    - row_potential[current]
                    - col_potential[candidate]
                )
                if reduced < slack[candidate]:
                    slack[candidate] = reduced
                    previous[candidate] = column
                if slack[candidate] < step:
                    step, next_column = slack[candidate], candidate
            row_potential[owner[used]] += step
            col_potential[used] -= step
            slack[~used] -= step
            column = next_column
            if owner[column] == 0:
                break
        while column:
            parent = previous[column]
            owner[column] = owner[parent]
            column = parent
    columns = np.flatnonzero(owner[1:])
    assigned_rows = owner[columns + 1] - 1
    order = np.argsort(assigned_rows, kind="stable")
    assigned_rows, columns = assigned_rows[order], columns[order]
    return (columns, assigned_rows) if transpose else (assigned_rows, columns)
