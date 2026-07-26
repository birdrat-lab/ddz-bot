from collections import Counter
from fractions import Fraction
import random

import pytest

from ddz_bot.cards import Rank, build_standard_deck
from ddz_bot.combinations import Play
from ddz_bot.game import (
    PASS_ACTION_KEY,
    BidAction,
    DouDizhuGame,
    GameConfig,
    GamePhase,
    GameState,
    MultiplierCause,
    Role,
)
from ddz_bot.rules import PayoffConvention, RuleSet


def test_new_hand_deals_standard_counts() -> None:
    game = DouDizhuGame(rng=random.Random(0))
    state = game.new_hand(starting_bidder=1)

    assert state.phase == GamePhase.BIDDING
    assert state.current_player == 1
    assert len(state.landlord_cards) == 3
    assert sum(state.hands[0].values()) == 17
    assert sum(state.hands[1].values()) == 17
    assert sum(state.hands[2].values()) == 17


def test_bidding_requires_strictly_higher_positive_bid() -> None:
    game = DouDizhuGame()
    state = game.new_hand(starting_bidder=0)

    game.apply_bid(state, 1)
    with pytest.raises(ValueError):
        game.apply_bid(state, 1)


def test_invalid_max_bid_is_rejected() -> None:
    with pytest.raises(ValueError):
        DouDizhuGame(GameConfig(rules=RuleSet(max_bid=0)))
    with pytest.raises(ValueError):
        DouDizhuGame(GameConfig(rules=RuleSet(max_bid=-1)))


def test_max_bid_one_is_accepted_and_ends_bidding_immediately() -> None:
    game = DouDizhuGame(GameConfig(rules=RuleSet(max_bid=1)))
    state = game.new_hand(starting_bidder=0)
    original_hand_size = sum(state.hands[0].values())

    game.apply_bid(state, 1)

    assert state.phase == GamePhase.PLAYING
    assert state.landlord == 0
    assert state.current_player == 0
    assert state.bid_history == [BidAction(player=0, bid=1)]
    assert sum(state.hands[0].values()) == original_hand_size + len(state.landlord_cards)


def test_bid_greater_than_max_bid_is_rejected_without_mutation() -> None:
    game = DouDizhuGame()
    state = game.new_hand(starting_bidder=0)
    snapshot = game.clone_state(state)

    with pytest.raises(ValueError):
        game.apply_bid(state, 4)

    assert state.bid_history == snapshot.bid_history
    assert state.current_player == snapshot.current_player
    assert state.current_bid == snapshot.current_bid
    assert state.hands == snapshot.hands


def test_bidding_ends_after_two_passes_following_high_bid() -> None:
    game = DouDizhuGame()
    state = game.new_hand(starting_bidder=0)

    game.apply_bid(state, 1)
    game.apply_bid(state, 0)
    game.apply_bid(state, 0)

    assert state.phase == GamePhase.PLAYING
    assert state.landlord == 0
    assert state.current_bid == 1
    assert state.current_player == 0


def test_three_initial_passes_produce_redeal() -> None:
    game = DouDizhuGame()
    state = game.new_hand(starting_bidder=1)

    game.apply_bid(state, 0)
    game.apply_bid(state, 0)
    game.apply_bid(state, 0)

    assert state.phase == GamePhase.REDEAL
    assert state.landlord is None
    assert state.current_player is None


def test_bidding_can_rotate_back_to_earlier_player() -> None:
    game = DouDizhuGame()
    state = game.new_hand(starting_bidder=0)

    game.apply_bid(state, 1)
    game.apply_bid(state, 0)
    game.apply_bid(state, 2)
    game.apply_bid(state, 0)
    game.apply_bid(state, 0)

    assert [action.bid for action in state.bid_history] == [1, 0, 2, 0, 0]
    assert state.landlord == 2
    assert state.phase == GamePhase.PLAYING


def test_pass_reset_returns_control_to_last_successful_player() -> None:
    game = DouDizhuGame()
    state = GameState(
        phase=GamePhase.PLAYING,
        hands=[
            Counter([Rank.THREE]),
            Counter([Rank.FOUR]),
            Counter([Rank.FIVE]),
        ],
        landlord_cards=(),
        starting_bidder=0,
        current_player=1,
        current_bid=1,
        highest_bidder=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        current_play=Play.from_cards([Rank.THREE]),
        current_play_owner=0,
        played_cards_by_player=[[], [], []],
        non_pass_play_counts=[1, 0, 0],
    )

    game.apply_play(state, None)
    assert state.current_player == 2
    assert state.current_play is not None

    game.apply_play(state, None)
    assert state.current_player == 0
    assert state.current_play is None


def test_rejected_action_does_not_mutate_state() -> None:
    game = DouDizhuGame()
    state = GameState(
        phase=GamePhase.PLAYING,
        hands=[
            Counter([Rank.THREE]),
            Counter([Rank.FOUR]),
            Counter([Rank.FIVE]),
        ],
        landlord_cards=(),
        starting_bidder=0,
        current_player=0,
        current_bid=1,
        highest_bidder=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        played_cards_by_player=[[], [], []],
        non_pass_play_counts=[0, 0, 0],
    )

    snapshot = game.clone_state(state)
    with pytest.raises(ValueError):
        game.apply_play(state, Play.from_cards([Rank.FOUR]))

    assert state.hands == snapshot.hands
    assert state.play_history == snapshot.play_history


def test_rejected_multiplier_play_does_not_mutate_state() -> None:
    game = DouDizhuGame()
    state = GameState(
        phase=GamePhase.PLAYING,
        hands=[
            Counter([Rank.THREE, Rank.THREE, Rank.THREE]),
            Counter([Rank.FOUR]),
            Counter([Rank.FIVE]),
        ],
        landlord_cards=(),
        starting_bidder=0,
        current_player=0,
        current_bid=1,
        highest_bidder=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        current_play=Play.from_cards([Rank.SIX]),
        current_play_owner=1,
        played_cards_by_player=[[], [], []],
        non_pass_play_counts=[0, 1, 0],
    )
    snapshot = game.clone_state(state)

    with pytest.raises(ValueError):
        game.apply_play(state, Play.from_cards([Rank.THREE, Rank.THREE, Rank.THREE]))

    assert state.hands == snapshot.hands
    assert state.play_history == snapshot.play_history
    assert state.multiplier_causes == snapshot.multiplier_causes
    assert state.current_player == snapshot.current_player


def test_conventional_scoring_and_spring_are_zero_sum() -> None:
    game = DouDizhuGame()
    state = GameState(
        phase=GamePhase.FINISHED,
        hands=[Counter(), Counter(), Counter()],
        landlord_cards=(),
        starting_bidder=0,
        current_player=None,
        current_bid=2,
        highest_bidder=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        winner=0,
        played_cards_by_player=[[], [], []],
        non_pass_play_counts=[3, 0, 0],
    )

    scores = game.score_hand(state)
    assert scores == (Fraction(8, 1), Fraction(-4, 1), Fraction(-4, 1))
    assert game.multiplier_causes_for_scoring(state) == (MultiplierCause.LANDLORD_SPRING,)


def test_anti_spring_applies_when_landlord_played_once() -> None:
    game = DouDizhuGame()
    state = GameState(
        phase=GamePhase.FINISHED,
        hands=[Counter(), Counter(), Counter()],
        landlord_cards=(),
        starting_bidder=0,
        current_player=None,
        current_bid=3,
        highest_bidder=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        winner=1,
        played_cards_by_player=[[], [], []],
        non_pass_play_counts=[1, 2, 1],
    )

    scores = game.score_hand(state)
    assert scores == (Fraction(-12, 1), Fraction(6, 1), Fraction(6, 1))
    assert game.multiplier_causes_for_scoring(state) == (MultiplierCause.PEASANT_ANTI_SPRING,)


def test_normalized_scoring_can_be_requested_explicitly() -> None:
    game = DouDizhuGame(GameConfig(rules=RuleSet(payoff_convention=PayoffConvention.NORMALIZED)))
    state = GameState(
        phase=GamePhase.FINISHED,
        hands=[Counter(), Counter(), Counter()],
        landlord_cards=(),
        starting_bidder=0,
        current_player=None,
        current_bid=3,
        highest_bidder=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        winner=1,
        played_cards_by_player=[[], [], []],
        non_pass_play_counts=[2, 3, 1],
    )

    scores = game.score_hand(state)
    assert scores == (Fraction(-3, 1), Fraction(3, 2), Fraction(3, 2))


def test_observation_hides_opponent_hands_and_shows_legal_actions_for_actor() -> None:
    game = DouDizhuGame()
    state = game.new_hand(starting_bidder=0)
    observation = game.observe(state, 0)

    assert len(observation.hand) == 17
    assert observation.landlord_cards == ()
    assert observation.legal_action_keys == tuple(game.encode_bid_action_key(bid) for bid in (0, 1, 2, 3))


def test_clone_state_is_independent() -> None:
    game = DouDizhuGame()
    state = game.new_hand(starting_bidder=0)
    clone = game.clone_state(state)

    clone.hands[0][Rank.THREE] += 1
    clone.bid_history.append(BidAction(player=0, bid=1))

    assert clone.hands[0] != state.hands[0]
    assert clone.bid_history != state.bid_history


def test_action_keys_round_trip() -> None:
    game = DouDizhuGame()
    play = Play.from_cards([Rank.THREE, Rank.THREE])
    assert game.decode_action_key(game.new_hand(0), game.encode_play_action_key(play)) == play
    assert game.decode_action_key(game.new_hand(0), PASS_ACTION_KEY) is None


def test_invalid_landlord_card_configuration_is_rejected() -> None:
    with pytest.raises(ValueError):
        DouDizhuGame(GameConfig(rules=RuleSet(landlord_card_count=2)))


def test_multiplier_event_history_and_scoring() -> None:
    game = DouDizhuGame()
    state = GameState(
        phase=GamePhase.FINISHED,
        hands=[Counter(), Counter(), Counter()],
        landlord_cards=(),
        starting_bidder=0,
        current_player=None,
        current_bid=2,
        highest_bidder=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        winner=0,
        multiplier_causes=[MultiplierCause.BOMB, MultiplierCause.ROCKET],
        played_cards_by_player=[[], [], []],
        non_pass_play_counts=[2, 0, 0],
    )

    assert game.multiplier_causes_for_scoring(state) == (
        MultiplierCause.BOMB,
        MultiplierCause.ROCKET,
        MultiplierCause.LANDLORD_SPRING,
    )
    assert game.score_hand(state) == (Fraction(32, 1), Fraction(-16, 1), Fraction(-16, 1))


def test_multiplier_event_history_with_peasant_anti_spring() -> None:
    game = DouDizhuGame()
    state = GameState(
        phase=GamePhase.FINISHED,
        hands=[Counter(), Counter(), Counter()],
        landlord_cards=(),
        starting_bidder=0,
        current_player=None,
        current_bid=1,
        highest_bidder=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        winner=1,
        multiplier_causes=[MultiplierCause.BOMB],
        played_cards_by_player=[[], [], []],
        non_pass_play_counts=[1, 2, 1],
    )

    assert game.multiplier_causes_for_scoring(state) == (
        MultiplierCause.BOMB,
        MultiplierCause.PEASANT_ANTI_SPRING,
    )
    assert game.score_hand(state) == (Fraction(-8, 1), Fraction(4, 1), Fraction(4, 1))


def test_seeded_random_playouts_are_reproducible_and_preserve_invariants() -> None:
    for seed in [0, 1, 2, 3, 4]:
        first = _run_seeded_episode(seed)
        second = _run_seeded_episode(seed)
        assert first == second


def test_bomb_event_is_recorded_end_to_end() -> None:
    game = DouDizhuGame()
    state = _playing_state(
        hands=[
            Counter([Rank.THREE, Rank.THREE, Rank.THREE, Rank.THREE, Rank.FIVE]),
            Counter([Rank.FOUR]),
            Counter([Rank.SIX]),
        ],
        current_player=0,
    )

    game.apply_play(state, Play.from_cards([Rank.THREE, Rank.THREE, Rank.THREE, Rank.THREE]))

    assert state.multiplier_causes == [MultiplierCause.BOMB]
    assert state.current_play == Play.from_cards([Rank.THREE, Rank.THREE, Rank.THREE, Rank.THREE])


def test_two_bombs_record_two_events_and_double_twice() -> None:
    game = DouDizhuGame()
    state = _playing_state(
        hands=[
            Counter([Rank.THREE, Rank.THREE, Rank.THREE, Rank.THREE, Rank.SEVEN]),
            Counter([Rank.FOUR, Rank.FOUR, Rank.FOUR, Rank.FOUR, Rank.EIGHT]),
            Counter([Rank.FIVE]),
        ],
        current_player=0,
    )

    game.apply_play(state, Play.from_cards([Rank.THREE, Rank.THREE, Rank.THREE, Rank.THREE]))
    game.apply_play(state, Play.from_cards([Rank.FOUR, Rank.FOUR, Rank.FOUR, Rank.FOUR]))
    game.apply_play(state, None)
    game.apply_play(state, None)
    game.apply_play(state, Play.from_cards([Rank.EIGHT]))

    assert state.multiplier_causes == [MultiplierCause.BOMB, MultiplierCause.BOMB]
    assert game.score_hand(state) == (Fraction(-16, 1), Fraction(8, 1), Fraction(8, 1))


def test_rocket_event_is_recorded_end_to_end() -> None:
    game = DouDizhuGame()
    state = _playing_state(
        hands=[
            Counter([Rank.BLACK_JOKER, Rank.RED_JOKER, Rank.THREE]),
            Counter([Rank.FOUR]),
            Counter([Rank.FIVE]),
        ],
        current_player=0,
    )

    game.apply_play(state, Play.from_cards([Rank.BLACK_JOKER, Rank.RED_JOKER]))

    assert state.multiplier_causes == [MultiplierCause.ROCKET]


def test_bomb_then_rocket_preserves_event_order_and_scoring() -> None:
    game = DouDizhuGame()
    state = _playing_state(
        hands=[
            Counter([Rank.THREE, Rank.THREE, Rank.THREE, Rank.THREE, Rank.SEVEN]),
            Counter([Rank.BLACK_JOKER, Rank.RED_JOKER, Rank.FOUR]),
            Counter([Rank.FIVE]),
        ],
        current_player=0,
    )

    game.apply_play(state, Play.from_cards([Rank.THREE, Rank.THREE, Rank.THREE, Rank.THREE]))
    game.apply_play(state, Play.from_cards([Rank.BLACK_JOKER, Rank.RED_JOKER]))
    game.apply_play(state, None)
    game.apply_play(state, None)
    game.apply_play(state, Play.from_cards([Rank.FOUR]))

    assert state.multiplier_causes == [MultiplierCause.BOMB, MultiplierCause.ROCKET]
    assert game.score_hand(state) == (Fraction(-16, 1), Fraction(8, 1), Fraction(8, 1))


def test_winning_play_clears_current_player() -> None:
    game = DouDizhuGame()
    state = _playing_state(
        hands=[Counter([Rank.THREE]), Counter([Rank.FOUR]), Counter([Rank.FIVE])],
        current_player=0,
    )

    game.apply_play(state, Play.from_cards([Rank.THREE]))

    assert state.phase == GamePhase.FINISHED
    assert state.current_player is None


def test_winning_bomb_clears_current_player() -> None:
    game = DouDizhuGame()
    state = _playing_state(
        hands=[Counter([Rank.THREE, Rank.THREE, Rank.THREE, Rank.THREE]), Counter([Rank.FOUR]), Counter([Rank.FIVE])],
        current_player=0,
    )

    game.apply_play(state, Play.from_cards([Rank.THREE, Rank.THREE, Rank.THREE, Rank.THREE]))

    assert state.phase == GamePhase.FINISHED
    assert state.current_player is None


def test_winning_rocket_clears_current_player() -> None:
    game = DouDizhuGame()
    state = _playing_state(
        hands=[Counter([Rank.BLACK_JOKER, Rank.RED_JOKER]), Counter([Rank.FOUR]), Counter([Rank.FIVE])],
        current_player=0,
    )

    game.apply_play(state, Play.from_cards([Rank.BLACK_JOKER, Rank.RED_JOKER]))

    assert state.phase == GamePhase.FINISHED
    assert state.current_player is None


def test_apply_play_after_completion_raises_without_mutation() -> None:
    game = DouDizhuGame()
    state = GameState(
        phase=GamePhase.FINISHED,
        hands=[Counter(), Counter([Rank.FOUR]), Counter([Rank.FIVE])],
        landlord_cards=(),
        starting_bidder=0,
        current_player=None,
        current_bid=1,
        highest_bidder=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        winner=0,
        played_cards_by_player=[[], [], []],
        non_pass_play_counts=[1, 0, 0],
    )
    snapshot = game.clone_state(state)

    with pytest.raises(ValueError):
        game.apply_play(state, Play.from_cards([Rank.FOUR]))

    assert state.hands == snapshot.hands
    assert state.play_history == snapshot.play_history
    assert state.current_player is None


def test_apply_bid_after_redeal_raises_without_mutation() -> None:
    game = DouDizhuGame()
    state = game.new_hand(starting_bidder=0)
    game.apply_bid(state, 0)
    game.apply_bid(state, 0)
    game.apply_bid(state, 0)
    snapshot = game.clone_state(state)

    with pytest.raises(ValueError):
        game.apply_bid(state, 1)

    assert state.bid_history == snapshot.bid_history
    assert state.current_player is None


def test_terminal_observations_expose_no_legal_actions() -> None:
    game = DouDizhuGame()
    state = GameState(
        phase=GamePhase.FINISHED,
        hands=[Counter(), Counter([Rank.FOUR]), Counter([Rank.FIVE])],
        landlord_cards=(),
        starting_bidder=0,
        current_player=None,
        current_bid=1,
        highest_bidder=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        winner=0,
        played_cards_by_player=[[], [], []],
        non_pass_play_counts=[1, 0, 0],
    )

    for player in range(3):
        assert game.observe(state, player).legal_action_keys is None


def _run_seeded_episode(seed: int) -> tuple:
    rng = random.Random(seed)
    game = DouDizhuGame(rng=random.Random(seed))
    state = game.new_hand()
    steps = 0
    action_limit = 512

    while state.phase in {GamePhase.BIDDING, GamePhase.PLAYING}:
        _assert_card_conservation(state)
        steps += 1
        if steps > action_limit:
            raise AssertionError(f"action limit exceeded: phase={state.phase} bids={state.bid_history} plays={state.play_history}")

        if state.phase == GamePhase.BIDDING:
            legal_bids = game.legal_bids(state)
            bid = rng.choice(legal_bids)
            assert bid in legal_bids
            game.apply_bid(state, bid)
            continue

        legal_plays = sorted(game.legal_plays(state), key=lambda play: play.cards)
        action_pool: list[Play | None] = list(legal_plays)
        if game.can_pass(state):
            action_pool.append(None)
        choice = rng.choice(action_pool)
        if choice is None:
            assert game.can_pass(state)
        else:
            assert choice in legal_plays
        game.apply_play(state, choice)
        assert all(count >= 0 for hand in state.hands for count in hand.values())

    _assert_card_conservation(state)
    if state.phase == GamePhase.REDEAL:
        assert state.winner is None
        return ("redeal", tuple(state.bid_history))

    assert state.phase == GamePhase.FINISHED
    assert state.winner is not None
    assert sum(state.hands[state.winner].values()) == 0
    scores = game.score_hand(state)
    assert sum(scores) == 0
    return (
        "finished",
        tuple(state.bid_history),
        tuple(state.play_history),
        state.winner,
        game.multiplier_causes_for_scoring(state),
        scores,
    )


def _assert_card_conservation(state: GameState) -> None:
    total = Counter()
    for hand in state.hands:
        total.update(hand)
    if not state.revealed_landlord_cards:
        total.update(state.landlord_cards)
    for played_cards in state.played_cards_by_player:
        total.update(played_cards)
    assert total == Counter(build_standard_deck())


def _playing_state(hands: list[Counter[Rank]], current_player: int) -> GameState:
    return GameState(
        phase=GamePhase.PLAYING,
        hands=hands,
        landlord_cards=(),
        starting_bidder=0,
        current_player=current_player,
        current_bid=1,
        highest_bidder=0,
        landlord=0,
        roles=[Role.LANDLORD, Role.PEASANT, Role.PEASANT],
        played_cards_by_player=[[], [], []],
        non_pass_play_counts=[0, 0, 0],
    )
