"""Scoring after every round."""


def round_score(bid: int, tricks_won: int) -> int:
    """Points for one round.

    - Bid hit exactly: 20 points + 10 per trick won.
    - Bid missed: -10 points per trick off (whether too many or too few).
    """
    if bid == tricks_won:
        return 20 + 10 * tricks_won
    return -10 * abs(bid - tricks_won)
