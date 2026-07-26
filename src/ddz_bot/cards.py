from __future__ import annotations

from collections import Counter
from enum import IntEnum


class Rank(IntEnum):
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14
    TWO = 15
    BLACK_JOKER = 16
    RED_JOKER = 17


SEQUENCE_CORE_RANKS = tuple(rank for rank in Rank if rank <= Rank.ACE)


def build_standard_deck() -> list[Rank]:
    deck: list[Rank] = []
    for rank in Rank:
        copies = 1 if rank in {Rank.BLACK_JOKER, Rank.RED_JOKER} else 4
        deck.extend([rank] * copies)
    return deck


def make_hand_counter(cards: list[Rank] | tuple[Rank, ...]) -> Counter[Rank]:
    return Counter(cards)
