from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from itertools import combinations

from .cards import Rank, SEQUENCE_CORE_RANKS


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
class Play:
    play_type: PlayType
    cards: tuple[Rank, ...]
    core_ranks: tuple[Rank, ...]
    attachment_ranks: tuple[Rank, ...] = ()

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
    def from_cards(cls, cards: list[Rank] | tuple[Rank, ...]) -> Play:
        normalized_cards = tuple(sorted(cards))
        if not normalized_cards:
            raise ValueError("play must contain at least one card")

        counts = Counter(normalized_cards)
        groups = sorted(counts.items(), key=lambda item: item[0])
        frequencies = sorted(counts.values(), reverse=True)
        unique_ranks = tuple(rank for rank, _ in groups)
        size = len(normalized_cards)

        if normalized_cards == (Rank.BLACK_JOKER, Rank.RED_JOKER):
            return cls(PlayType.ROCKET, normalized_cards, normalized_cards)

        if len(groups) == 1:
            rank = unique_ranks[0]
            if size == 1:
                return cls(PlayType.SINGLE, normalized_cards, (rank,))
            if size == 2:
                return cls(PlayType.PAIR, normalized_cards, (rank,))
            if size == 3:
                return cls(PlayType.TRIPLET, normalized_cards, (rank,))
            if size == 4:
                return cls(PlayType.BOMB, normalized_cards, (rank,))

        if size == 4 and frequencies == [3, 1]:
            trip_rank = _ranks_with_count(counts, 3)[0]
            attachment = tuple(rank for rank, count in groups for _ in range(count) if rank != trip_rank)
            return cls(PlayType.TRIPLET_SINGLE, normalized_cards, (trip_rank,), attachment)

        if size == 5 and frequencies == [3, 2]:
            trip_rank = _ranks_with_count(counts, 3)[0]
            pair_rank = _ranks_with_count(counts, 2)[0]
            return cls(PlayType.TRIPLET_PAIR, normalized_cards, (trip_rank,), (pair_rank, pair_rank))

        if _is_straight(counts):
            return cls(PlayType.STRAIGHT, normalized_cards, unique_ranks)

        if _is_consecutive_pairs(counts):
            return cls(PlayType.CONSECUTIVE_PAIRS, normalized_cards, unique_ranks)

        airplane = _parse_airplane(normalized_cards, counts)
        if airplane is not None:
            return airplane

        if size == 6 and 4 in counts.values():
            quad_rank = _ranks_with_count(counts, 4)[0]
            attachments = tuple(rank for rank, count in groups for _ in range(count) if rank != quad_rank)
            return cls(PlayType.FOUR_WITH_TWO_SINGLES, normalized_cards, (quad_rank,), attachments)

        if size == 8 and frequencies == [4, 2, 2]:
            quad_rank = _ranks_with_count(counts, 4)[0]
            attachment_ranks = tuple(
                rank for rank, count in groups for _ in range(count) if rank != quad_rank
            )
            return cls(PlayType.FOUR_WITH_TWO_PAIRS, normalized_cards, (quad_rank,), attachment_ranks)

        raise ValueError(f"illegal play: {normalized_cards}")


def generate_legal_plays(hand: Counter[Rank], current_play: Play | None = None) -> set[Play]:
    plays = _generate_all_plays(hand)
    if current_play is None:
        return plays
    return {play for play in plays if play.can_beat(current_play)}


def _generate_all_plays(hand: Counter[Rank]) -> set[Play]:
    plays: set[Play] = set()
    ranks = sorted(hand)
    sequence_ranks = [rank for rank in ranks if rank in SEQUENCE_CORE_RANKS]

    for rank in ranks:
        plays.add(Play(PlayType.SINGLE, (rank,), (rank,)))
        if hand[rank] >= 2:
            plays.add(Play(PlayType.PAIR, (rank, rank), (rank,)))
        if hand[rank] >= 3:
            plays.add(Play(PlayType.TRIPLET, (rank, rank, rank), (rank,)))
        if hand[rank] >= 4:
            plays.add(Play(PlayType.BOMB, (rank, rank, rank, rank), (rank,)))

    if hand[Rank.BLACK_JOKER] and hand[Rank.RED_JOKER]:
        plays.add(
            Play(
                PlayType.ROCKET,
                (Rank.BLACK_JOKER, Rank.RED_JOKER),
                (Rank.BLACK_JOKER, Rank.RED_JOKER),
            )
        )

    for trip_rank in [rank for rank in ranks if hand[rank] >= 3]:
        for kicker in ranks:
            if kicker == trip_rank:
                continue
            plays.add(
                Play(
                    PlayType.TRIPLET_SINGLE,
                    tuple(sorted((trip_rank, trip_rank, trip_rank, kicker))),
                    (trip_rank,),
                    (kicker,),
                )
            )
        for pair_rank in [rank for rank in ranks if rank != trip_rank and hand[rank] >= 2]:
            plays.add(
                Play(
                    PlayType.TRIPLET_PAIR,
                    tuple(sorted((trip_rank, trip_rank, trip_rank, pair_rank, pair_rank))),
                    (trip_rank,),
                    (pair_rank, pair_rank),
                )
            )

    for sequence in _all_consecutive_sequences(sequence_ranks, lambda rank: hand[rank] >= 1, minimum_length=5):
        for length in range(5, len(sequence) + 1):
            for start in range(0, len(sequence) - length + 1):
                core = tuple(sequence[start : start + length])
                plays.add(Play(PlayType.STRAIGHT, core, core))

    for sequence in _all_consecutive_sequences(sequence_ranks, lambda rank: hand[rank] >= 2, minimum_length=3):
        for length in range(3, len(sequence) + 1):
            for start in range(0, len(sequence) - length + 1):
                core = tuple(sequence[start : start + length])
                cards = tuple(sorted(rank for rank in core for _ in range(2)))
                plays.add(Play(PlayType.CONSECUTIVE_PAIRS, cards, core))

    for sequence in _all_consecutive_sequences(sequence_ranks, lambda rank: hand[rank] >= 3, minimum_length=2):
        for length in range(2, len(sequence) + 1):
            for start in range(0, len(sequence) - length + 1):
                core = tuple(sequence[start : start + length])
                base_hand = hand.copy()
                for rank in core:
                    base_hand[rank] -= 3
                    if base_hand[rank] == 0:
                        del base_hand[rank]
                base_cards = tuple(sorted(rank for rank in core for _ in range(3)))
                plays.add(Play(PlayType.AIRPLANE, base_cards, core))

                for attachments in _choose_multiset_cards(base_hand, length):
                    cards = tuple(sorted(base_cards + attachments))
                    plays.add(Play(PlayType.AIRPLANE_SINGLES, cards, core, attachments))

                for pair_ranks in combinations(sorted(rank for rank in base_hand if base_hand[rank] >= 2), length):
                    attachments = tuple(sorted(rank for rank in pair_ranks for _ in range(2)))
                    cards = tuple(sorted(base_cards + attachments))
                    plays.add(Play(PlayType.AIRPLANE_PAIRS, cards, core, attachments))

    for quad_rank in [rank for rank in ranks if hand[rank] >= 4]:
        residual = hand.copy()
        residual[quad_rank] -= 4
        if residual[quad_rank] == 0:
            del residual[quad_rank]
        quad_cards = (quad_rank, quad_rank, quad_rank, quad_rank)
        for attachments in _choose_multiset_cards(residual, 2):
            plays.add(
                Play(
                    PlayType.FOUR_WITH_TWO_SINGLES,
                    tuple(sorted(quad_cards + attachments)),
                    (quad_rank,),
                    attachments,
                )
            )
        for pair_ranks in combinations(sorted(rank for rank in residual if residual[rank] >= 2), 2):
            attachments = tuple(sorted(rank for rank in pair_ranks for _ in range(2)))
            plays.add(
                Play(
                    PlayType.FOUR_WITH_TWO_PAIRS,
                    tuple(sorted(quad_cards + attachments)),
                    (quad_rank,),
                    attachments,
                )
            )

    return plays


def _parse_airplane(cards: tuple[Rank, ...], counts: Counter[Rank]) -> Play | None:
    trip_ranks = tuple(sorted(rank for rank, count in counts.items() if count == 3))
    if len(trip_ranks) < 2 or not _ranks_are_consecutive(trip_ranks):
        return None

    attachments = tuple(
        sorted(rank for rank, count in counts.items() if count < 3 for _ in range(count))
    )
    triplet_cards = tuple(sorted(rank for rank in trip_ranks for _ in range(3)))
    trip_count = len(trip_ranks)

    if len(cards) == trip_count * 3:
        return Play(PlayType.AIRPLANE, cards, trip_ranks)
    if len(cards) == trip_count * 4 and len(attachments) == trip_count:
        return Play(PlayType.AIRPLANE_SINGLES, cards, trip_ranks, attachments)
    if len(cards) == trip_count * 5 and len(attachments) == trip_count * 2:
        attachment_counts = Counter(attachments)
        if all(count == 2 for count in attachment_counts.values()):
            return Play(PlayType.AIRPLANE_PAIRS, cards, trip_ranks, attachments)
    if triplet_cards == cards:
        return Play(PlayType.AIRPLANE, cards, trip_ranks)
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


def _choose_multiset_cards(hand: Counter[Rank], total_cards: int) -> set[tuple[Rank, ...]]:
    ranks = sorted(hand)
    results: set[tuple[Rank, ...]] = set()

    def backtrack(index: int, remaining: int, chosen: list[Rank]) -> None:
        if remaining == 0:
            results.add(tuple(chosen))
            return
        if index == len(ranks):
            return

        rank = ranks[index]
        max_take = min(hand[rank], remaining)
        for take in range(max_take + 1):
            chosen.extend([rank] * take)
            backtrack(index + 1, remaining - take, chosen)
            for _ in range(take):
                chosen.pop()

    backtrack(0, total_cards, [])
    results.discard(())
    return results
