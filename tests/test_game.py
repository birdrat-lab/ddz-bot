from collections import Counter
from fractions import Fraction
import random

from ddz_bot.cards import Rank
from ddz_bot.combinations import Play
from ddz_bot.game import DouDizhuGame, GameConfig, GamePhase, GameState, Role


def test_new_hand_deals_standard_counts() -> None:
    game = DouDizhuGame(rng=random.Random(0))
    state = game.new_hand(starting_bidder=1)

    assert state.phase == GamePhase.BIDDING
    assert state.current_player == 1
    assert len(state.landlord_cards) == 3
    assert sum(state.hands[0].values()) == 17
    assert sum(state.hands[1].values()) == 17
    assert sum(state.hands[2].values()) == 17


def test_max_bid_ends_bidding_immediately() -> None:
    game = DouDizhuGame()
    state = game.new_hand(starting_bidder=0)

    game.apply_bid(state, 3)

    assert state.phase == GamePhase.PLAYING
    assert state.landlord == 0
    assert state.base_stake == 3
    assert state.current_player == 0
    assert state.roles[0] == Role.LANDLORD
    assert sum(state.hands[0].values()) == 20


def test_last_bidder_cannot_bid_zero_after_two_zero_bids() -> None:
    game = DouDizhuGame()
    state = game.new_hand(starting_bidder=1)

    game.apply_bid(state, 0)
    game.apply_bid(state, 0)

    try:
        game.apply_bid(state, 0)
    except ValueError as exc:
        assert "must bid at least 1" in str(exc)
    else:
        raise AssertionError("last bidder should not be allowed to bid zero")


def test_last_bidder_may_choose_any_positive_bid_after_two_zero_bids() -> None:
    game = DouDizhuGame()
    state = game.new_hand(starting_bidder=1)

    game.apply_bid(state, 0)
    game.apply_bid(state, 0)
    game.apply_bid(state, 3)

    assert state.phase == GamePhase.PLAYING
    assert state.landlord == 0
    assert state.base_stake == 3


def test_pass_reset_returns_control_to_last_successful_player() -> None:
    game = DouDizhuGame()
    state = GameState(
        phase=GamePhase.PLAYING,
        hands=[
            Counter([Rank.THREE]),
            Counter([Rank.FOUR]),
            Counter([Rank.FIVE]),
        ],
        bids=[1, 0, 0],
        landlord_cards=(),
        starting_bidder=0,
        current_player=1,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        current_play=Play.from_cards([Rank.THREE]),
        current_play_owner=0,
        base_stake=1,
    )

    game.apply_play(state, None)
    assert state.current_player == 2
    assert state.current_play is not None

    game.apply_play(state, None)
    assert state.current_player == 0
    assert state.current_play is None


def test_score_hand_with_doubling_is_zero_sum() -> None:
    game = DouDizhuGame(GameConfig())
    state = GameState(
        phase=GamePhase.FINISHED,
        hands=[Counter(), Counter(), Counter()],
        bids=[3, 0, 1],
        landlord_cards=(),
        starting_bidder=0,
        current_player=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        winner=1,
        base_stake=3,
        multiplier_events=2,
    )

    scores = game.score_hand(state)
    assert scores == (Fraction(-12, 1), Fraction(6, 1), Fraction(6, 1))


def test_apply_play_reaches_terminal_state() -> None:
    game = DouDizhuGame()
    state = GameState(
        phase=GamePhase.PLAYING,
        hands=[
            Counter([Rank.THREE]),
            Counter([Rank.FOUR]),
            Counter([Rank.FIVE]),
        ],
        bids=[1, 0, 0],
        landlord_cards=(),
        starting_bidder=0,
        current_player=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        base_stake=1,
    )

    game.apply_play(state, Play.from_cards([Rank.THREE]))

    assert state.phase == GamePhase.FINISHED
    assert state.winner == 0
