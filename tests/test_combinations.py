from collections import Counter

import pytest

from ddz_bot.cards import Rank
from ddz_bot.combinations import Play, PlayType, generate_legal_plays


def test_parse_rocket() -> None:
    play = Play.from_cards([Rank.BLACK_JOKER, Rank.RED_JOKER])
    assert play.play_type == PlayType.ROCKET


def test_parse_straight_excludes_two_and_jokers() -> None:
    play = Play.from_cards([Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN])
    assert play.play_type == PlayType.STRAIGHT

    with pytest.raises(ValueError):
        Play.from_cards([Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE, Rank.TWO])


def test_four_with_two_singles_rejects_pair_split() -> None:
    with pytest.raises(ValueError):
        Play.from_cards(
            [
                Rank.THREE,
                Rank.THREE,
                Rank.THREE,
                Rank.THREE,
                Rank.FOUR,
                Rank.FOUR,
            ]
        )


def test_airplane_single_wings_must_be_distinct() -> None:
    with pytest.raises(ValueError):
        Play.from_cards(
            [
                Rank.THREE,
                Rank.THREE,
                Rank.THREE,
                Rank.FOUR,
                Rank.FOUR,
                Rank.FOUR,
                Rank.SEVEN,
                Rank.SEVEN,
            ]
        )


def test_airplane_single_wings_reject_double_jokers() -> None:
    with pytest.raises(ValueError):
        Play.from_cards(
            [
                Rank.THREE,
                Rank.THREE,
                Rank.THREE,
                Rank.FOUR,
                Rank.FOUR,
                Rank.FOUR,
                Rank.BLACK_JOKER,
                Rank.RED_JOKER,
            ]
        )


def test_generated_plays_round_trip_through_classifier() -> None:
    hand = Counter(
        [
            Rank.THREE,
            Rank.THREE,
            Rank.THREE,
            Rank.FOUR,
            Rank.FOUR,
            Rank.FOUR,
            Rank.FIVE,
            Rank.SIX,
            Rank.SEVEN,
            Rank.EIGHT,
        ]
    )
    for play in generate_legal_plays(hand):
        assert Play.from_cards(play.cards) == play


def test_response_filter_only_keeps_beating_plays() -> None:
    hand = Counter(
        [
            Rank.FIVE,
            Rank.FIVE,
            Rank.SIX,
            Rank.SIX,
            Rank.SEVEN,
            Rank.SEVEN,
            Rank.EIGHT,
            Rank.EIGHT,
            Rank.NINE,
            Rank.NINE,
            Rank.RED_JOKER,
            Rank.BLACK_JOKER,
        ]
    )
    current_play = Play.from_cards([Rank.THREE, Rank.THREE, Rank.FOUR, Rank.FOUR, Rank.FIVE, Rank.FIVE])
    responses = generate_legal_plays(hand, current_play)

    assert Play.from_cards([Rank.SIX, Rank.SIX, Rank.SEVEN, Rank.SEVEN, Rank.EIGHT, Rank.EIGHT]) in responses
    assert Play.from_cards([Rank.BLACK_JOKER, Rank.RED_JOKER]) in responses
    assert Play.from_cards([Rank.FIVE]) not in responses
