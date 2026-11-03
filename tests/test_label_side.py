"""label_side: puts a scatter label on the left when a close neighbour would overlap it."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from dashboard import label_side  # noqa: E402


def sides(points):
    """points: {name: (supply, account)} -> {name: side}"""
    pairs = pd.DataFrame(
        [(name, supply, account) for name, (supply, account) in points.items()],
        columns=["name", "supply", "account"],
    )
    return dict(zip(pairs["name"], label_side(pairs)))


def test_close_neighbours_split_left_and_right():
    # Same height and 10% apart on a log axis: the left point's label moves to the left.
    assert sides({"A": (40, 60.0), "B": (44, 60.5)}) == {"A": "left", "B": "right"}


def test_far_apart_on_x_both_right():
    assert sides({"A": (40, 60.0), "B": (300, 60.0)}) == {"A": "right", "B": "right"}


def test_different_heights_both_right():
    # Close on x but far apart on y: labels are on different lines, no overlap.
    assert sides({"A": (40, 50.0), "B": (44, 70.0)}) == {"A": "right", "B": "right"}


def test_single_point_goes_right():
    assert sides({"A": (40, 60.0)}) == {"A": "right"}
