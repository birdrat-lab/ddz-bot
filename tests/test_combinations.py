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


def assert_generated_plays_are_valid(hand: Counter[Rank]) -> set[Play]:
    positive_part = Counter({rank: count for rank, count in hand.items() if count > 0})
    plays = generate_legal_plays(hand)
    for play in plays:
        generated = Counter(play.cards)
        for rank, count in generated.items():
            assert count <= positive_part[rank]
        assert Play.from_cards(play.cards) == play
    return plays


def test_quad_heavy_generation_invariants_two_adjacent_quads() -> None:
    hand = Counter(
        [
            Rank.THREE, Rank.THREE, Rank.THREE, Rank.THREE,
            Rank.FOUR, Rank.FOUR, Rank.FOUR, Rank.FOUR,
        ]
    )
    plays = assert_generated_plays_are_valid(hand)
    assert Play.from_cards([Rank.THREE, Rank.THREE, Rank.THREE, Rank.FOUR, Rank.FOUR, Rank.FOUR]) in plays
    assert all(not (play.play_type == PlayType.AIRPLANE_SINGLES and len(play.cards) == 8) for play in plays)


def test_quad_heavy_generation_invariants_three_adjacent_quads() -> None:
    hand = Counter(
        [
            Rank.THREE, Rank.THREE, Rank.THREE, Rank.THREE,
            Rank.FOUR, Rank.FOUR, Rank.FOUR, Rank.FOUR,
            Rank.FIVE, Rank.FIVE, Rank.FIVE, Rank.FIVE,
        ]
    )
    assert_generated_plays_are_valid(hand)


def test_airplane_generation_with_external_quads_and_valid_wings() -> None:
    hand = Counter(
        [
            Rank.THREE, Rank.THREE, Rank.THREE,
            Rank.FOUR, Rank.FOUR, Rank.FOUR,
            Rank.SEVEN, Rank.SEVEN, Rank.SEVEN, Rank.SEVEN,
            Rank.EIGHT,
            Rank.NINE,
            Rank.TEN, Rank.TEN,
            Rank.JACK, Rank.JACK,
        ]
    )
    plays = assert_generated_plays_are_valid(hand)
    assert Play.from_cards([Rank.THREE, Rank.THREE, Rank.THREE, Rank.FOUR, Rank.FOUR, Rank.FOUR, Rank.EIGHT, Rank.NINE]) in plays
    assert Play.from_cards([Rank.THREE, Rank.THREE, Rank.THREE, Rank.FOUR, Rank.FOUR, Rank.FOUR, Rank.TEN, Rank.TEN, Rank.JACK, Rank.JACK]) in plays


def test_airplane_generation_rejects_longer_single_wings_with_both_jokers() -> None:
    with pytest.raises(ValueError):
        Play.from_cards(
            [
                Rank.THREE, Rank.THREE, Rank.THREE,
                Rank.FOUR, Rank.FOUR, Rank.FOUR,
                Rank.FIVE, Rank.FIVE, Rank.FIVE,
                Rank.BLACK_JOKER, Rank.RED_JOKER, Rank.SIX,
            ]
        )


def test_airplane_generation_accepts_longer_single_wings_with_one_joker() -> None:
    play = Play.from_cards(
        [
            Rank.THREE, Rank.THREE, Rank.THREE,
            Rank.FOUR, Rank.FOUR, Rank.FOUR,
            Rank.FIVE, Rank.FIVE, Rank.FIVE,
            Rank.BLACK_JOKER, Rank.SIX, Rank.SEVEN,
        ]
    )
    assert play.play_type == PlayType.AIRPLANE_SINGLES


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


def test_zero_count_filtering_does_not_generate_absent_card() -> None:
    hand = Counter({Rank.THREE: 0, Rank.FOUR: 1})
    original = hand.copy()
    plays = generate_legal_plays(hand)

    assert Play.from_cards([Rank.THREE]) not in plays
    assert Play.from_cards([Rank.FOUR]) in plays
    assert hand == original


def test_negative_count_rejection() -> None:
    with pytest.raises(ValueError):
        generate_legal_plays(Counter({Rank.THREE: -1}))


def test_mixed_valid_and_invalid_counts_are_rejected() -> None:
    with pytest.raises(ValueError):
        generate_legal_plays(Counter({Rank.THREE: 1, Rank.FOUR: -1}))


def test_zero_count_round_trip_invariants() -> None:
    hand = Counter({Rank.THREE: 0, Rank.FOUR: 2, Rank.FIVE: 1})
    positive_part = Counter({Rank.FOUR: 2, Rank.FIVE: 1})
    for play in generate_legal_plays(hand):
        assert Counter(play.cards) <= positive_part
        assert Play.from_cards(play.cards) == play
