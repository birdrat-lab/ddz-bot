from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PayoffConvention(str, Enum):
    CONVENTIONAL = "conventional"
    NORMALIZED = "normalized"


@dataclass(frozen=True, slots=True)
class RuleSet:
    max_bid: int = 3
    landlord_card_count: int = 3
    forbid_core_rank_attachments: bool = True
    require_distinct_airplane_single_wings: bool = True
    require_distinct_airplane_pair_wings: bool = True
    require_distinct_four_with_two_single_wings: bool = True
    require_distinct_four_with_two_pair_wings: bool = True
    forbid_double_joker_single_attachments: bool = True
    enable_spring: bool = True
    enable_anti_spring: bool = True
    payoff_convention: PayoffConvention = PayoffConvention.CONVENTIONAL


DEFAULT_RULESET = RuleSet()
