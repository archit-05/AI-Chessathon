"""Calibration of the shipped net's systematic bias by piece count and material imbalance
(tools/calib_table.py over the site's depth-16 labelled positions, slope 1.083): evaluate()
subtracts CALIB[pieces * 11 + imbalance + 5] (centipawns, side-to-move view, imbalance clipped
to +-5 pawns). A tuned evaluation term: constants, no lookup of positions."""
import numpy as np

CALIB = np.array([
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 0 pieces
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 1 pieces
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 2 pieces
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,  # 3 pieces
    0, 0, 0, -212, 0, 4, 0, 226, 0, 0, 0,  # 4 pieces
    0, 0, -24, 0, -32, 0, 77, 0, 31, 0, 0,  # 5 pieces
    0, -98, 0, -106, 0, 19, 0, 124, 0, 0, 0,  # 6 pieces
    -250, 0, -66, 0, -70, 0, 108, 0, 118, 0, 0,  # 7 pieces
    0, -159, 0, -31, 0, 13, 0, 57, 0, 197, 0,  # 8 pieces
    -323, 0, -66, 0, -28, 0, 67, 0, 100, 0, 356,  # 9 pieces
    -370, -106, 0, 7, 0, 18, 0, 36, 0, 140, 0,  # 10 pieces
    -272, 0, -63, 0, -4, 0, 40, 0, 87, 0, 324,  # 11 pieces
    -264, -95, 0, 30, 0, 20, 0, 13, 0, 175, 329,  # 12 pieces
    -163, 0, -4, 0, 9, 0, 21, 0, 47, 0, 216,  # 13 pieces
    -168, -27, 0, 50, 0, 17, 0, -26, 0, 65, 0,  # 14 pieces
    -109, 0, 49, 0, 27, 0, -1, 0, -16, 0, 151,  # 15 pieces
    -66, 2, 0, 71, 0, 14, 0, -33, 0, 32, 0,  # 16 pieces
    -53, 0, 68, 0, 29, 0, -7, 0, -43, 0, 113,  # 17 pieces
    41, 72, 0, 81, 0, 8, 0, -61, 0, -19, 0,  # 18 pieces
    94, 0, 88, 0, 29, 0, -10, 0, -59, 0, -47,  # 19 pieces
    0, 96, 0, 71, 0, 7, 0, -53, 0, -52, 0,  # 20 pieces
    121, 0, 84, 0, 38, 0, -29, 0, -58, 0, 0,  # 21 pieces
    0, 99, 0, 75, 0, 3, 0, -66, 0, -64, 0,  # 22 pieces
    0, 0, 103, 0, 33, 0, -29, 0, -88, 0, 0,  # 23 pieces
    0, 0, 0, 73, 0, 2, 0, -69, 0, 0, 0,  # 24 pieces
    0, 0, 90, 0, 36, 0, -32, 0, -93, 0, 0,  # 25 pieces
    0, 0, 0, 78, 0, 1, 0, -79, 0, 0, 0,  # 26 pieces
    0, 0, 0, 0, 24, 0, -30, 0, 0, 0, 0,  # 27 pieces
    0, 0, 0, 95, 0, 1, 0, -103, 0, 0, 0,  # 28 pieces
    0, 0, 0, 0, 18, 0, -19, 0, 0, 0, 0,  # 29 pieces
    0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0,  # 30 pieces
    0, 0, 0, 0, 10, 0, -28, 0, 0, 0, 0,  # 31 pieces
    0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0,  # 32 pieces
], dtype=np.int64)
