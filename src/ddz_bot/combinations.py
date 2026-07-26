from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from itertools import combinations

from .cards import Rank, SEQUENCE_CORE_RANKS
from .rules import DEFAULT_RULESET, RuleSet


class PlayType(str, Enum):
    SINGLE = "single"
    PAIR = "pair"
    TRIPLET = "triplet"
    TRIPLET_SINGLE = "triplet_single"
    TRIPLET_PAIR = "triplet_pair"
    STRAIGHT = "straight"
    CONSECUTIVE_PAIRS = "consecutive_pairs"
    AIRPLANE = "airplane"
    AIRPLANE_SINGLES = "airplane_singles"
    AIRPLANE_PAIRS = "airplane_pairs"
    FOUR_WITH_TWO_SINGLES = "four_with_two_singles"
    FOUR_WITH_TWO_PAIRS = "four_with_two_pairs"
    BOMB = "bomb"
    ROCKET = "rocket"


@dataclass(frozen=True, slots=True)
class _PlaySpec:
    play_type: PlayType
    cards: tuple[Rank, ...]
    core_ranks: tuple[Rank, ...]
    attachment_ranks: tuple[Rank, ...] = ()


@dataclass(frozen=True, slots=True)
class Play:
    play_type: PlayType
    cards: tuple[Rank, ...]
    core_ranks: tuple[Rank, ...]
    attachment_ranks: tuple[Rank, ...] = ()

    def __post_init__(self) -> None:
        spec = _classify_cards(self.cards)
        if (
            spec.play_type != self.play_type
            or spec.cards != self.cards
            or spec.core_ranks != self.core_ranks
            or spec.attachment_ranks != self.attachment_ranks
        ):
            raise ValueError("inconsistent play specification")

    @property
    def size(self) -> int:
        return len(self.cards)

    @property
    def comparison_rank(self) -> Rank:
        if self.play_type == PlayType.ROCKET:
            return Rank.RED_JOKER
        return max(self.core_ranks)

    @property
    def doubles_stake(self) -> bool:
        return self.play_type in {PlayType.BOMB, PlayType.ROCKET}

    def can_beat(self, other: Play) -> bool:
        if self.play_type == PlayType.ROCKET:
            return other.play_type != PlayType.ROCKET
        if other.play_type == PlayType.ROCKET:
            return False
        if self.play_type == PlayType.BOMB and other.play_type != PlayType.BOMB:
            return True
        if self.play_type != other.play_type:
            return False
        if self.size != other.size:
            return False
        return self.comparison_rank > other.comparison_rank

    @classmethod
    def from_cards(
        cls,
        cards: Iterable[Rank],
        rules: RuleSet = DEFAULT_RULESET,
    ) -> Play:
        del rules
        spec = _classify_cards(tuple(cards))
        return cls._from_spec(spec)

    @classmethod
    def _from_spec(cls, spec: _PlaySpec) -> Play:
        return cls(spec.play_type, spec.cards, spec.core_ranks, spec.attachment_ranks)


def generate_legal_plays(
    hand: Counter[Rank],
    current_play: Play | None = None,
    rules: RuleSet = DEFAULT_RULESET,
) -> set[Play]:
    del rules
    plays = _generate_all_plays(hand)
    if current_play is None:
        return plays
    return {play for play in plays if play.can_beat(current_play)}


def _classify_cards(cards: Iterable[Rank]) -> _PlaySpec:
    normalized_cards = tuple(sorted(cards))
    if not normalized_cards:
        raise ValueError("play must contain at least one card")

    counts = Counter(normalized_cards)
    groups = sorted(counts.items(), key=lambda item: item[0])
    frequencies = sorted(counts.values(), reverse=True)
    unique_ranks = tuple(rank for rank, _ in groups)
    size = len(normalized_cards)

    if normalized_cards == (Rank.BLACK_JOKER, Rank.RED_JOKER):
        return _PlaySpec(PlayType.ROCKET, normalized_cards, normalized_cards)

    if len(groups) == 1:
        rank = unique_ranks[0]
        if size == 1:
            return _PlaySpec(PlayType.SINGLE, normalized_cards, (rank,))
        if size == 2:
            return _PlaySpec(PlayType.PAIR, normalized_cards, (rank,))
        if size == 3:
            return _PlaySpec(PlayType.TRIPLET, normalized_cards, (rank,))
        if size == 4:
            return _PlaySpec(PlayType.BOMB, normalized_cards, (rank,))

    if size == 4 and frequencies == [3, 1]:
        trip_rank = _ranks_with_count(counts, 3)[0]
        attachment = tuple(rank for rank, count in groups for _ in range(count) if rank != trip_rank)
        return _PlaySpec(PlayType.TRIPLET_SINGLE, normalized_cards, (trip_rank,), attachment)

    if size == 5 and frequencies == [3, 2]:
        trip_rank = _ranks_with_count(counts, 3)[0]
        pair_rank = _ranks_with_count(counts, 2)[0]
        return _PlaySpec(PlayType.TRIPLET_PAIR, normalized_cards, (trip_rank,), (pair_rank, pair_rank))

    if _is_straight(counts):
        return _PlaySpec(PlayType.STRAIGHT, normalized_cards, unique_ranks)

    if _is_consecutive_pairs(counts):
        return _PlaySpec(PlayType.CONSECUTIVE_PAIRS, normalized_cards, unique_ranks)

    airplane = _parse_airplane(normalized_cards, counts)
    if airplane is not None:
        return airplane

    if size == 6 and 4 in counts.values():
        quad_rank = _ranks_with_count(counts, 4)[0]
        attachment_counts = Counter(rank for rank in normalized_cards if rank != quad_rank)
        if len(attachment_counts) != 2 or any(count != 1 for count in attachment_counts.values()):
            raise ValueError(f"illegal play: {normalized_cards}")
        if _contains_both_jokers(tuple(attachment_counts)):
            raise ValueError(f"illegal play: {normalized_cards}")
        attachments = tuple(sorted(attachment_counts))
        return _PlaySpec(PlayType.FOUR_WITH_TWO_SINGLES, normalized_cards, (quad_rank,), attachments)

    if size == 8 and frequencies == [4, 2, 2]:
        quad_rank = _ranks_with_count(counts, 4)[0]
        attachment_counts = Counter(rank for rank in normalized_cards if rank != quad_rank)
        if len(attachment_counts) != 2 or any(count != 2 for count in attachment_counts.values()):
            raise ValueError(f"illegal play: {normalized_cards}")
        attachments = tuple(sorted(rank for rank in attachment_counts for _ in range(2)))
        return _PlaySpec(PlayType.FOUR_WITH_TWO_PAIRS, normalized_cards, (quad_rank,), attachments)

    raise ValueError(f"illegal play: {normalized_cards}")


def _generate_all_plays(hand: Counter[Rank]) -> set[Play]:
    plays: set[Play] = set()
    ranks = sorted(hand)
    sequence_ranks = [rank for rank in ranks if rank in SEQUENCE_CORE_RANKS]

    for rank in ranks:
        plays.add(Play.from_cards((rank,)))
        if hand[rank] >= 2:
            plays.add(Play.from_cards((rank, rank)))
        if hand[rank] >= 3:
            plays.add(Play.from_cards((rank, rank, rank)))
        if hand[rank] >= 4:
            plays.add(Play.from_cards((rank, rank, rank, rank)))

    if hand[Rank.BLACK_JOKER] >= 1 and hand[Rank.RED_JOKER] >= 1:
        plays.add(Play.from_cards((Rank.BLACK_JOKER, Rank.RED_JOKER)))

    for trip_rank in [rank for rank in ranks if hand[rank] >= 3]:
        for kicker in [rank for rank in ranks if rank != trip_rank]:
            plays.add(Play.from_cards((trip_rank, trip_rank, trip_rank, kicker)))
        for pair_rank in [rank for rank in ranks if rank != trip_rank and hand[rank] >= 2]:
            plays.add(Play.from_cards((trip_rank, trip_rank, trip_rank, pair_rank, pair_rank)))

    for sequence in _all_consecutive_sequences(sequence_ranks, lambda rank: hand[rank] >= 1, minimum_length=5):
        for core in _all_slices(sequence, minimum_length=5):
            plays.add(Play.from_cards(core))

    for sequence in _all_consecutive_sequences(sequence_ranks, lambda rank: hand[rank] >= 2, minimum_length=3):
        for core in _all_slices(sequence, minimum_length=3):
            plays.add(Play.from_cards(tuple(sorted(rank for rank in core for _ in range(2)))))

    for sequence in _all_consecutive_sequences(sequence_ranks, lambda rank: hand[rank] >= 3, minimum_length=2):
        for core in _all_slices(sequence, minimum_length=2):
            base_cards = tuple(sorted(rank for rank in core for _ in range(3)))
            plays.add(Play.from_cards(base_cards))

            eligible_single_wings = [rank for rank in ranks if rank not in core and hand[rank] >= 1]
            for wing_ranks in combinations(eligible_single_wings, len(core)):
                if _contains_both_jokers(wing_ranks):
                    continue
                plays.add(Play.from_cards(tuple(sorted(base_cards + tuple(wing_ranks)))))

            eligible_pair_wings = [rank for rank in ranks if rank not in core and hand[rank] >= 2]
            for pair_ranks in combinations(eligible_pair_wings, len(core)):
                attachment_cards = tuple(sorted(rank for rank in pair_ranks for _ in range(2)))
                plays.add(Play.from_cards(tuple(sorted(base_cards + attachment_cards))))

    for quad_rank in [rank for rank in ranks if hand[rank] >= 4]:
        quad_cards = (quad_rank, quad_rank, quad_rank, quad_rank)
        eligible_single_wings = [rank for rank in ranks if rank != quad_rank and hand[rank] >= 1]
        for wing_ranks in combinations(eligible_single_wings, 2):
            if _contains_both_jokers(wing_ranks):
                continue
            plays.add(Play.from_cards(tuple(sorted(quad_cards + wing_ranks))))

        eligible_pair_wings = [rank for rank in ranks if rank != quad_rank and hand[rank] >= 2]
        for pair_ranks in combinations(eligible_pair_wings, 2):
            attachment_cards = tuple(sorted(rank for rank in pair_ranks for _ in range(2)))
            plays.add(Play.from_cards(tuple(sorted(quad_cards + attachment_cards))))

    return plays


def _parse_airplane(cards: tuple[Rank, ...], counts: Counter[Rank]) -> _PlaySpec | None:
    trip_ranks = tuple(sorted(rank for rank, count in counts.items() if count == 3))
    if len(trip_ranks) < 2 or not _ranks_are_consecutive(trip_ranks):
        return None

    attachment_counts = Counter(rank for rank in counts if rank not in trip_ranks for _ in range(counts[rank]))
    trip_count = len(trip_ranks)

    if len(cards) == trip_count * 3 and not attachment_counts:
        return _PlaySpec(PlayType.AIRPLANE, cards, trip_ranks)

    if len(cards) == trip_count * 4:
        if len(attachment_counts) != trip_count or any(count != 1 for count in attachment_counts.values()):
            raise ValueError(f"illegal play: {cards}")
        if _contains_both_jokers(tuple(attachment_counts)):
            raise ValueError(f"illegal play: {cards}")
        attachments = tuple(sorted(attachment_counts))
        return _PlaySpec(PlayType.AIRPLANE_SINGLES, cards, trip_ranks, attachments)

    if len(cards) == trip_count * 5:
        if len(attachment_counts) != trip_count or any(count != 2 for count in attachment_counts.values()):
            raise ValueError(f"illegal play: {cards}")
        attachments = tuple(sorted(rank for rank in attachment_counts for _ in range(2)))
        return _PlaySpec(PlayType.AIRPLANE_PAIRS, cards, trip_ranks, attachments)

    return None


def _is_straight(counts: Counter[Rank]) -> bool:
    ranks = tuple(sorted(counts))
    return len(ranks) >= 5 and all(count == 1 for count in counts.values()) and _ranks_are_consecutive(ranks)


def _is_consecutive_pairs(counts: Counter[Rank]) -> bool:
    ranks = tuple(sorted(counts))
    return len(ranks) >= 3 and all(count == 2 for count in counts.values()) and _ranks_are_consecutive(ranks)


def _ranks_are_consecutive(ranks: tuple[Rank, ...]) -> bool:
    if not ranks:
        return False
    if any(rank > Rank.ACE for rank in ranks):
        return False
    return all(right - left == 1 for left, right in zip(ranks, ranks[1:]))


def _ranks_with_count(counts: Counter[Rank], frequency: int) -> tuple[Rank, ...]:
    return tuple(sorted(rank for rank, count in counts.items() if count == frequency))


def _all_consecutive_sequences(
    ranks: list[Rank],
    predicate: callable,
    minimum_length: int,
) -> list[list[Rank]]:
    sequences: list[list[Rank]] = []
    current: list[Rank] = []
    for rank in ranks:
        if not predicate(rank):
            if len(current) >= minimum_length:
                sequences.append(current)
            current = []
            continue
        if current and rank != current[-1] + 1:
            if len(current) >= minimum_length:
                sequences.append(current)
            current = [rank]
        else:
            current.append(rank)
    if len(current) >= minimum_length:
        sequences.append(current)
    return sequences


def _all_slices(sequence: list[Rank], minimum_length: int) -> list[tuple[Rank, ...]]:
    slices: list[tuple[Rank, ...]] = []
    for length in range(minimum_length, len(sequence) + 1):
        for start in range(0, len(sequence) - length + 1):
            slices.append(tuple(sequence[start : start + length]))
    return slices


def _contains_both_jokers(ranks: tuple[Rank, ...]) -> bool:
    return {Rank.BLACK_JOKER, Rank.RED_JOKER}.issubset(set(ranks))
