from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
import random

from .cards import Rank, build_standard_deck
from .combinations import Play, generate_legal_plays
from .rules import DEFAULT_RULESET, PayoffConvention, RuleSet


PASS_ACTION_KEY = ("pass", ())


class GamePhase(str, Enum):
    BIDDING = "bidding"
    PLAYING = "playing"
    FINISHED = "finished"
    REDEAL = "redeal"


class Role(str, Enum):
    LANDLORD = "landlord"
    PEASANT = "peasant"


class MultiplierCause(str, Enum):
    BOMB = "bomb"
    ROCKET = "rocket"
    LANDLORD_SPRING = "landlord_spring"
    PEASANT_ANTI_SPRING = "peasant_anti_spring"


@dataclass(frozen=True, slots=True)
class BidAction:
    player: int
    bid: int


@dataclass(frozen=True, slots=True)
class PlayAction:
    player: int
    play: Play | None


@dataclass(frozen=True, slots=True)
class Observation:
    player: int
    role: Role | None
    hand: tuple[Rank, ...]
    current_player: int | None
    landlord: int | None
    landlord_cards: tuple[Rank, ...]
    current_play: Play | None
    current_play_owner: int | None
    bid_history: tuple[BidAction, ...]
    play_history: tuple[PlayAction, ...]
    played_cards_by_player: tuple[tuple[Rank, ...], ...]
    remaining_card_counts: tuple[int, ...]
    multiplier_causes: tuple[MultiplierCause, ...]
    legal_action_keys: tuple[tuple[str, tuple[int, ...]], ...] | None


@dataclass(frozen=True, slots=True)
class GameConfig:
    num_players: int = 3
    rules: RuleSet = DEFAULT_RULESET


@dataclass(slots=True)
class GameState:
    phase: GamePhase
    hands: list[Counter[Rank]]
    landlord_cards: tuple[Rank, ...]
    starting_bidder: int
    current_player: int | None
    bid_history: list[BidAction] = field(default_factory=list)
    play_history: list[PlayAction] = field(default_factory=list)
    current_bid: int = 0
    highest_bidder: int | None = None
    consecutive_bid_passes: int = 0
    initial_bid_passes: int = 0
    landlord: int | None = None
    roles: list[Role | None] = field(default_factory=list)
    current_play: Play | None = None
    current_play_owner: int | None = None
    consecutive_play_passes: int = 0
    multiplier_causes: list[MultiplierCause] = field(default_factory=list)
    winner: int | None = None
    revealed_landlord_cards: bool = False
    played_cards_by_player: list[list[Rank]] = field(default_factory=list)
    non_pass_play_counts: list[int] = field(default_factory=list)


class DouDizhuGame:
    def __init__(self, config: GameConfig | None = None, rng: random.Random | None = None) -> None:
        self.config = config or GameConfig()
        self.rng = rng or random.Random()
        if self.config.num_players != 3:
            raise ValueError("this kernel currently supports the standard 3-player baseline only")
        self._validate_config()

    def new_hand(self, starting_bidder: int | None = None) -> GameState:
        deck = build_standard_deck()
        self.rng.shuffle(deck)
        starting = self.rng.randrange(self.config.num_players) if starting_bidder is None else starting_bidder
        if not 0 <= starting < self.config.num_players:
            raise ValueError("starting bidder out of range")

        landlord_count = self.config.rules.landlord_card_count
        cards_per_player, remainder = divmod(len(deck) - landlord_count, self.config.num_players)
        if remainder != 0:
            raise ValueError("configuration does not produce an even private deal")

        hands = [
            Counter(deck[index * cards_per_player : (index + 1) * cards_per_player])
            for index in range(self.config.num_players)
        ]
        landlord_cards = tuple(sorted(deck[cards_per_player * self.config.num_players :]))
        if len(landlord_cards) != landlord_count:
            raise ValueError("dealt landlord card count does not match configuration")

        return GameState(
            phase=GamePhase.BIDDING,
            hands=hands,
            landlord_cards=landlord_cards,
            starting_bidder=starting,
            current_player=starting,
            roles=[None] * self.config.num_players,
            played_cards_by_player=[[] for _ in range(self.config.num_players)],
            non_pass_play_counts=[0] * self.config.num_players,
        )

    def clone_state(self, state: GameState) -> GameState:
        return GameState(
            phase=state.phase,
            hands=[Counter(hand) for hand in state.hands],
            landlord_cards=tuple(state.landlord_cards),
            starting_bidder=state.starting_bidder,
            current_player=state.current_player,
            bid_history=list(state.bid_history),
            play_history=list(state.play_history),
            current_bid=state.current_bid,
            highest_bidder=state.highest_bidder,
            consecutive_bid_passes=state.consecutive_bid_passes,
            initial_bid_passes=state.initial_bid_passes,
            landlord=state.landlord,
            roles=list(state.roles),
            current_play=state.current_play,
            current_play_owner=state.current_play_owner,
            consecutive_play_passes=state.consecutive_play_passes,
            multiplier_causes=list(state.multiplier_causes),
            winner=state.winner,
            revealed_landlord_cards=state.revealed_landlord_cards,
            played_cards_by_player=[list(cards) for cards in state.played_cards_by_player],
            non_pass_play_counts=list(state.non_pass_play_counts),
        )

    def legal_bids(self, state: GameState) -> tuple[int, ...]:
        if state.phase != GamePhase.BIDDING or state.current_player is None:
            raise ValueError("legal bids are only available during bidding")
        bids = [0]
        bids.extend(range(state.current_bid + 1, self.config.rules.max_bid + 1))
        return tuple(bids)

    def apply_bid(self, state: GameState, bid: int) -> GameState:
        if state.phase != GamePhase.BIDDING or state.current_player is None:
            raise ValueError("bids are only allowed during the bidding phase")
        if bid not in self.legal_bids(state):
            raise ValueError("illegal bid for current auction state")

        player = state.current_player
        action = BidAction(player=player, bid=bid)

        if bid == 0:
            if state.current_bid == 0:
                state.initial_bid_passes += 1
                state.bid_history.append(action)
                if state.initial_bid_passes >= self.config.num_players:
                    state.phase = GamePhase.REDEAL
                    state.current_player = None
                    return state
            else:
                state.consecutive_bid_passes += 1
                state.bid_history.append(action)
                if state.consecutive_bid_passes >= self.config.num_players - 1:
                    self._finalize_landlord(state, state.highest_bidder)
                    return state
        else:
            state.bid_history.append(action)
            state.current_bid = bid
            state.highest_bidder = player
            state.consecutive_bid_passes = 0
            state.initial_bid_passes = 0
            if bid == self.config.rules.max_bid:
                self._finalize_landlord(state, player)
                return state

        state.current_player = (player + 1) % self.config.num_players
        return state

    def legal_plays(self, state: GameState, player: int | None = None) -> set[Play]:
        if state.phase != GamePhase.PLAYING or state.current_player is None:
            raise ValueError("legal plays are only available during the playing phase")
        acting_player = state.current_player if player is None else player
        if acting_player != state.current_player:
            raise ValueError("legal plays can only be requested for the current player")
        return generate_legal_plays(state.hands[acting_player], state.current_play)

    def can_pass(self, state: GameState) -> bool:
        return state.phase == GamePhase.PLAYING and state.current_play is not None

    def apply_play(self, state: GameState, play: Play | None) -> GameState:
        if state.phase != GamePhase.PLAYING or state.current_player is None:
            raise ValueError("plays are only allowed during the playing phase")

        player = state.current_player
        hand = state.hands[player]

        if play is None:
            if state.current_play is None:
                raise ValueError("cannot pass when leading a fresh trick")
            state.play_history.append(PlayAction(player=player, play=None))
            state.consecutive_play_passes += 1
            if state.consecutive_play_passes >= self.config.num_players - 1:
                if state.current_play_owner is None:
                    raise ValueError("missing current play owner during reset")
                state.current_player = state.current_play_owner
                state.current_play = None
                state.current_play_owner = None
                state.consecutive_play_passes = 0
            else:
                state.current_player = (player + 1) % self.config.num_players
            return state

        legal_plays = self.legal_plays(state)
        if play not in legal_plays:
            raise ValueError(f"illegal play for current state: {play}")
        if any(hand[rank] <= 0 for rank in play.cards):
            raise ValueError("player does not have the specified cards")

        for rank in play.cards:
            hand[rank] -= 1
            if hand[rank] == 0:
                del hand[rank]

        state.play_history.append(PlayAction(player=player, play=play))
        state.played_cards_by_player[player].extend(play.cards)
        state.non_pass_play_counts[player] += 1
        state.current_play = play
        state.current_play_owner = player
        state.consecutive_play_passes = 0
        if play.play_type == play.play_type.BOMB:
            state.multiplier_causes.append(MultiplierCause.BOMB)
        elif play.play_type == play.play_type.ROCKET:
            state.multiplier_causes.append(MultiplierCause.ROCKET)

        if not hand:
            state.phase = GamePhase.FINISHED
            state.winner = player
            state.current_player = None
            return state

        state.current_player = (player + 1) % self.config.num_players
        return state

    def score_hand(self, state: GameState) -> tuple[Fraction, ...]:
        if state.phase != GamePhase.FINISHED or state.winner is None or state.landlord is None:
            raise ValueError("hand must be finished before scoring")

        causes = list(state.multiplier_causes)
        if self._is_landlord_spring(state):
            causes.append(MultiplierCause.LANDLORD_SPRING)
        if self._is_peasant_anti_spring(state):
            causes.append(MultiplierCause.PEASANT_ANTI_SPRING)

        stake = state.current_bid * (2 ** len(causes))
        landlord = state.landlord
        scores = [Fraction(0, 1) for _ in range(self.config.num_players)]

        if self.config.rules.payoff_convention == PayoffConvention.NORMALIZED:
            peasant_share = Fraction(stake, self.config.num_players - 1)
            if state.winner == landlord:
                scores[landlord] = Fraction(stake, 1)
                for player in range(self.config.num_players):
                    if player != landlord:
                        scores[player] = -peasant_share
            else:
                scores[landlord] = Fraction(-stake, 1)
                for player in range(self.config.num_players):
                    if player != landlord:
                        scores[player] = peasant_share
        else:
            if state.winner == landlord:
                scores[landlord] = Fraction(2 * stake, 1)
                for player in range(self.config.num_players):
                    if player != landlord:
                        scores[player] = Fraction(-stake, 1)
            else:
                scores[landlord] = Fraction(-2 * stake, 1)
                for player in range(self.config.num_players):
                    if player != landlord:
                        scores[player] = Fraction(stake, 1)

        if sum(scores) != 0:
            raise AssertionError("score checksum failed")
        return tuple(scores)

    def multiplier_causes_for_scoring(self, state: GameState) -> tuple[MultiplierCause, ...]:
        causes = list(state.multiplier_causes)
        if state.phase == GamePhase.FINISHED:
            if self._is_landlord_spring(state):
                causes.append(MultiplierCause.LANDLORD_SPRING)
            if self._is_peasant_anti_spring(state):
                causes.append(MultiplierCause.PEASANT_ANTI_SPRING)
        return tuple(causes)

    def observe(self, state: GameState, player: int) -> Observation:
        if not 0 <= player < self.config.num_players:
            raise ValueError("player out of range")

        legal_action_keys: tuple[tuple[str, tuple[int, ...]], ...] | None = None
        if state.current_player == player:
            if state.phase == GamePhase.BIDDING:
                legal_action_keys = tuple(self.encode_bid_action_key(bid) for bid in self.legal_bids(state))
            elif state.phase == GamePhase.PLAYING:
                play_keys = [self.encode_play_action_key(play) for play in sorted(self.legal_plays(state), key=lambda p: p.cards)]
                if self.can_pass(state):
                    play_keys.append(PASS_ACTION_KEY)
                legal_action_keys = tuple(play_keys)

        public_landlord_cards = state.landlord_cards if state.revealed_landlord_cards else ()
        return Observation(
            player=player,
            role=state.roles[player],
            hand=tuple(sorted(rank for rank, count in state.hands[player].items() for _ in range(count))),
            current_player=state.current_player,
            landlord=state.landlord,
            landlord_cards=public_landlord_cards,
            current_play=state.current_play,
            current_play_owner=state.current_play_owner,
            bid_history=tuple(state.bid_history),
            play_history=tuple(state.play_history),
            played_cards_by_player=tuple(tuple(cards) for cards in state.played_cards_by_player),
            remaining_card_counts=tuple(sum(hand.values()) for hand in state.hands),
            multiplier_causes=self.multiplier_causes_for_scoring(state),
            legal_action_keys=legal_action_keys,
        )

    def encode_play_action_key(self, play: Play | None) -> tuple[str, tuple[int, ...]]:
        if play is None:
            return PASS_ACTION_KEY
        return ("play", tuple(int(rank) for rank in play.cards))

    def encode_bid_action_key(self, bid: int) -> tuple[str, tuple[int, ...]]:
        return ("bid", (bid,))

    def decode_action_key(self, state: GameState, action_key: tuple[str, tuple[int, ...]]) -> int | Play | None:
        kind, payload = action_key
        if kind == "pass":
            if payload:
                raise ValueError("pass payload must be empty")
            return None
        if kind == "bid":
            if len(payload) != 1:
                raise ValueError("bid payload must contain exactly one integer")
            return payload[0]
        if kind == "play":
            return Play.from_cards(Rank(value) for value in payload)
        raise ValueError("unknown action key")

    def _validate_config(self) -> None:
        if self.config.rules.max_bid < 1:
            raise ValueError("max_bid must be at least 1")
        landlord_count = self.config.rules.landlord_card_count
        if landlord_count < 0:
            raise ValueError("landlord card count must be non-negative")
        if (54 - landlord_count) % self.config.num_players != 0:
            raise ValueError("landlord card count must leave an even private deal")

    def _finalize_landlord(self, state: GameState, landlord: int | None) -> None:
        if landlord is None or state.current_bid <= 0:
            raise ValueError("cannot finalize landlord without a positive high bid")
        state.landlord = landlord
        state.phase = GamePhase.PLAYING
        state.current_player = landlord
        state.roles = [
            Role.LANDLORD if player == landlord else Role.PEASANT
            for player in range(self.config.num_players)
        ]
        state.revealed_landlord_cards = True
        for rank in state.landlord_cards:
            state.hands[landlord][rank] += 1

    def _is_landlord_spring(self, state: GameState) -> bool:
        if not self.config.rules.enable_spring or state.winner != state.landlord or state.landlord is None:
            return False
        return all(
            state.non_pass_play_counts[player] == 0
            for player in range(self.config.num_players)
            if player != state.landlord
        )

    def _is_peasant_anti_spring(self, state: GameState) -> bool:
        if not self.config.rules.enable_anti_spring or state.landlord is None or state.winner == state.landlord:
            return False
        return state.non_pass_play_counts[state.landlord] == 1
