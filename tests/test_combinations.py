from collections import Counter

from ddz_bot.cards import Rank
from ddz_bot.combinations import Play, PlayType, generate_legal_plays


def test_parse_rocket() -> None:
    play = Play.from_cards([Rank.BLACK_JOKER, Rank.RED_JOKER])
    assert play.play_type == PlayType.ROCKET


def test_parse_straight_excludes_two_and_jokers() -> None:
    play = Play.from_cards([Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN])
    assert play.play_type == PlayType.STRAIGHT

    try:
        Play.from_cards([Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE, Rank.TWO])
    except ValueError:
        pass
    else:
        raise AssertionError("straight with a two should be illegal")


def test_parse_airplane_with_pairs() -> None:
    play = Play.from_cards(
        [
            Rank.THREE,
            Rank.THREE,
            Rank.THREE,
            Rank.FOUR,
            Rank.FOUR,
            Rank.FOUR,
            Rank.SEVEN,
            Rank.SEVEN,
            Rank.EIGHT,
            Rank.EIGHT,
        ]
    )
    assert play.play_type == PlayType.AIRPLANE_PAIRS
    assert play.core_ranks == (Rank.THREE, Rank.FOUR)


def test_bomb_and_rocket_override_comparison() -> None:
    straight = Play.from_cards([Rank.THREE, Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN])
    bomb = Play.from_cards([Rank.NINE, Rank.NINE, Rank.NINE, Rank.NINE])
    rocket = Play.from_cards([Rank.BLACK_JOKER, Rank.RED_JOKER])

    assert bomb.can_beat(straight)
    assert rocket.can_beat(bomb)


def test_generate_legal_plays_includes_broken_bomb_lines() -> None:
    hand = Counter(
        [
            Rank.THREE,
            Rank.THREE,
            Rank.THREE,
            Rank.THREE,
            Rank.FOUR,
            Rank.FOUR,
            Rank.FIVE,
        ]
    )
    plays = generate_legal_plays(hand)

    assert Play.from_cards([Rank.THREE]) in plays
    assert Play.from_cards([Rank.THREE, Rank.THREE]) in plays
    assert Play.from_cards([Rank.THREE, Rank.THREE, Rank.THREE]) in plays
    assert Play.from_cards([Rank.THREE, Rank.THREE, Rank.THREE, Rank.THREE]) in plays
    assert Play.from_cards([Rank.THREE, Rank.THREE, Rank.THREE, Rank.FOUR]) in plays


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
