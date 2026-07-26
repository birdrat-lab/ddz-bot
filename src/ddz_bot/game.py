from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
import random

from .cards import Rank, build_standard_deck
from .combinations import Play, generate_legal_plays


class GamePhase(str, Enum):
    BIDDING = "bidding"
    PLAYING = "playing"
    FINISHED = "finished"


class Role(str, Enum):
    LANDLORD = "landlord"
    PEASANT = "peasant"


@dataclass(slots=True)
class GameConfig:
    num_players: int = 3
    max_bid: int = 3
    landlord_bonus_cards: int = 3


@dataclass(slots=True)
class GameState:
    phase: GamePhase
    hands: list[Counter[Rank]]
    bids: list[int | None]
    landlord_cards: tuple[Rank, ...]
    starting_bidder: int
    current_player: int
    current_bid: int = 0
    highest_bidder: int | None = None
    bidding_turns_taken: int = 0
    landlord: int | None = None
    roles: list[Role | None] = field(default_factory=list)
    current_play: Play | None = None
    current_play_owner: int | None = None
    consecutive_passes: int = 0
    multiplier_events: int = 0
    winner: int | None = None
    base_stake: int = 0


class DouDizhuGame:
    def __init__(self, config: GameConfig | None = None, rng: random.Random | None = None) -> None:
        self.config = config or GameConfig()
        self.rng = rng or random.Random()
        if self.config.num_players != 3:
            raise ValueError("this kernel currently supports the standard 3-player baseline only")

    def new_hand(self, starting_bidder: int | None = None) -> GameState:
        deck = build_standard_deck()
        self.rng.shuffle(deck)
        starting = self.rng.randrange(self.config.num_players) if starting_bidder is None else starting_bidder
        if not 0 <= starting < self.config.num_players:
            raise ValueError("starting bidder out of range")

        cards_per_player = (len(deck) - self.config.landlord_bonus_cards) // self.config.num_players
        hands = [
            Counter(deck[index * cards_per_player : (index + 1) * cards_per_player])
            for index in range(self.config.num_players)
        ]
        landlord_cards = tuple(sorted(deck[cards_per_player * self.config.num_players :]))
        return GameState(
            phase=GamePhase.BIDDING,
            hands=hands,
            bids=[None] * self.config.num_players,
            landlord_cards=landlord_cards,
            starting_bidder=starting,
            current_player=starting,
            roles=[None] * self.config.num_players,
        )

    def apply_bid(self, state: GameState, bid: int) -> GameState:
        if state.phase != GamePhase.BIDDING:
            raise ValueError("bids are only allowed during the bidding phase")
        if not 0 <= bid <= self.config.max_bid:
            raise ValueError("bid out of range")
        if state.bids[state.current_player] is not None:
            raise ValueError("player already bid")
        if self._last_bidder_must_open(state) and bid == 0:
            raise ValueError("last bidder must bid at least 1 when all prior bids are 0")

        player = state.current_player
        state.bids[player] = bid
        state.bidding_turns_taken += 1

        if bid > state.current_bid:
            state.current_bid = bid
            state.highest_bidder = player

        if bid == self.config.max_bid:
            self._finalize_landlord(state, player, bid)
            return state

        if state.bidding_turns_taken >= self.config.num_players:
            if state.highest_bidder is None or state.current_bid <= 0:
                raise AssertionError("bidding ended without a valid positive landlord bid")
            landlord = state.highest_bidder
            base_stake = state.current_bid
            self._finalize_landlord(state, landlord, base_stake)
            return state

        state.current_player = (player + 1) % self.config.num_players
        return state

    def legal_plays(self, state: GameState, player: int | None = None) -> set[Play]:
        if state.phase != GamePhase.PLAYING:
            raise ValueError("legal plays are only available during the playing phase")
        acting_player = state.current_player if player is None else player
        if acting_player != state.current_player:
            raise ValueError("legal plays can only be requested for the current player")
        return generate_legal_plays(state.hands[acting_player], state.current_play)

    def can_pass(self, state: GameState) -> bool:
        return state.phase == GamePhase.PLAYING and state.current_play is not None

    def apply_play(self, state: GameState, play: Play | None) -> GameState:
        if state.phase != GamePhase.PLAYING:
            raise ValueError("plays are only allowed during the playing phase")

        player = state.current_player
        hand = state.hands[player]

        if play is None:
            if state.current_play is None:
                raise ValueError("cannot pass when leading a fresh trick")
            state.consecutive_passes += 1
            if state.consecutive_passes >= self.config.num_players - 1:
                if state.current_play_owner is None:
                    raise ValueError("missing current play owner during reset")
                state.current_player = state.current_play_owner
                state.current_play = None
                state.current_play_owner = None
                state.consecutive_passes = 0
            else:
                state.current_player = (player + 1) % self.config.num_players
            return state

        legal_plays = self.legal_plays(state)
        if play not in legal_plays:
            raise ValueError(f"illegal play for current state: {play}")

        for rank in play.cards:
            if hand[rank] <= 0:
                raise ValueError("player does not have the specified cards")
            hand[rank] -= 1
            if hand[rank] == 0:
                del hand[rank]

        state.current_play = play
        state.current_play_owner = player
        state.consecutive_passes = 0
        if play.doubles_stake:
            state.multiplier_events += 1

        if not hand:
            state.phase = GamePhase.FINISHED
            state.winner = player
            return state

        state.current_player = (player + 1) % self.config.num_players
        return state

    def score_hand(self, state: GameState) -> tuple[Fraction, ...]:
        if state.phase != GamePhase.FINISHED or state.winner is None or state.landlord is None:
            raise ValueError("hand must be finished before scoring")

        stake = state.base_stake * (2 ** state.multiplier_events)
        landlord = state.landlord
        peasant_share = Fraction(stake, self.config.num_players - 1)
        scores = [Fraction(0, 1) for _ in range(self.config.num_players)]

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

        if sum(scores) != 0:
            raise AssertionError("score checksum failed")
        return tuple(scores)

    def _finalize_landlord(self, state: GameState, landlord: int, base_stake: int) -> None:
        state.landlord = landlord
        state.base_stake = base_stake
        state.phase = GamePhase.PLAYING
        state.current_player = landlord
        state.roles = [
            Role.LANDLORD if player == landlord else Role.PEASANT
            for player in range(self.config.num_players)
        ]
        for rank in state.landlord_cards:
            state.hands[landlord][rank] += 1

    def _last_bidder_must_open(self, state: GameState) -> bool:
        if state.bidding_turns_taken != self.config.num_players - 1:
            return False
        return state.current_bid == 0 and state.highest_bidder is None
