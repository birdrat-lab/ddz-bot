# AGENTS.md

## Scope

This is a narrow correctness and API-cleanup pass for the existing Dou Dizhu kernel.

Do not add new agents, search algorithms, reinforcement learning, user interfaces, networking, or broader rule variants during this pass.

Implement only the following changes:

1. End-to-end bomb and rocket multiplier-event tests.
2. Positive `max_bid` validation.
3. Positive hand-count filtering and invalid-count rejection.
4. Clear `current_player` when a game finishes.
5. Remove or explicitly deprecate ignored `rules` parameters in combination APIs.

Keep the complete test suite passing after each coherent change.

---

## 1. Test bomb and rocket events end to end

### Problem

Current scoring tests may construct `multiplier_causes` manually. That verifies arithmetic but does not prove that playing an actual bomb or rocket records the correct multiplier event.

### Required behavior

When `apply_play` accepts a bomb:

- Append exactly one `MultiplierCause.BOMB`.
- Double the effective stake exactly once.
- Preserve event order relative to earlier and later multiplier events.

When `apply_play` accepts a rocket:

- Append exactly one `MultiplierCause.ROCKET`.
- Double the effective stake exactly once.
- Preserve event order.

A rejected play must not append a multiplier event.

### Required tests

Add transition-level tests that use actual hands, legal plays, and `apply_play`.

At minimum:

#### Single bomb

- Construct a playing state in which the current player holds a legal bomb.
- Apply the bomb.
- Assert that exactly one `BOMB` event was appended.
- Assert the resulting multiplier or final stake doubled once.

#### Two bombs

- Play one bomb.
- Advance through a legal sequence that permits another bomb.
- Play the second bomb.
- Assert that two distinct `BOMB` events exist.
- Assert that the stake reflects two doublings.

#### Single rocket

- Construct a state in which the current player holds both jokers.
- Apply the rocket.
- Assert that exactly one `ROCKET` event was appended.
- Assert the stake doubled once.

#### Bomb followed by rocket

- Play a bomb and later a rocket.
- Assert event order:

```python
[
    MultiplierCause.BOMB,
    MultiplierCause.ROCKET,
]
```

- Assert that both doublings affect final scoring.

#### Rejected multiplier play

- Attempt an illegal bomb or rocket action.
- Assert that:
  - the hand is unchanged,
  - play history is unchanged,
  - multiplier events are unchanged,
  - current player is unchanged.

Do not test only a cached multiplier integer. Inspect the named multiplier-event history.

---

## 2. Validate `max_bid`

### Problem

A ruleset with `max_bid <= 0` makes the auction invalid or guarantees an all-pass redeal.

### Required behavior

Reject invalid bidding configuration before a game is dealt or bidding begins.

At minimum:

```python
if rules.max_bid < 1:
    raise ValueError("max_bid must be at least 1")
```

Place this validation in the existing configuration-validation path so every game instance receives the same check.

Do not silently replace an invalid value with a default.

### Required tests

Add tests for:

- `max_bid = 0` raises `ValueError`.
- Negative `max_bid` raises `ValueError`.
- `max_bid = 1` is accepted.
- Bidding exactly `max_bid` ends the auction immediately.
- A bid greater than `max_bid` is rejected without mutating state.

For the immediate-termination test, assert:

- phase changes to playing,
- the high bidder becomes landlord,
- landlord cards are transferred exactly once,
- bid history contains the accepted maximum bid,
- the next player is the landlord.

---

## 3. Normalize and validate hand counters

### Problem

Public combination-generation functions may receive a `Counter` containing zero or negative entries.

A zero-count key must not generate a card that is absent from the hand. Negative multiplicities indicate invalid input and must not be interpreted as a legal hand.

### Required behavior

At the public boundary for play generation:

- Ignore ranks whose multiplicity is exactly zero.
- Reject any negative multiplicity with `ValueError`.
- Generate plays only from strictly positive counts.
- Preserve ordinary `Counter` semantics for valid positive hands.

A suitable normalization pattern is:

```python
for rank, count in hand.items():
    if count < 0:
        raise ValueError("hand counts must be nonnegative")

normalized = Counter(
    {
        rank: count
        for rank, count in hand.items()
        if count > 0
    }
)
```

Use the normalized hand for all generation and containment checks.

Do not mutate the caller's `Counter`.

### Required tests

Add tests for:

#### Zero-count filtering

```python
hand = Counter(
    {
        Rank.THREE: 0,
        Rank.FOUR: 1,
    }
)
```

Assert:

- no single `THREE` is generated,
- single `FOUR` is generated,
- the original `Counter` is unchanged.

#### Negative count rejection

```python
hand = Counter({Rank.THREE: -1})
```

Assert `generate_legal_plays` raises `ValueError`.

#### Mixed valid and invalid counts

A hand containing positive and negative entries must be rejected entirely. Do not partially generate from the positive subset.

#### Round-trip invariants after normalization

For a hand with zero-count keys:

```python
for play in generate_legal_plays(hand):
    assert Counter(play.cards) <= positive_part_of_hand
    assert Play.from_cards(play.cards) == play
```

---

## 4. Clear `current_player` on completion

### Problem

A finished game may retain the winning player in `current_player`, even though no further action is legal.

### Required state invariant

Use the following invariant:

```text
BIDDING or PLAYING:
    current_player is an integer player index

FINISHED or REDEAL:
    current_player is None
```

When a player empties their hand:

- set the winner,
- change phase to `FINISHED`,
- set `current_player = None`,
- do not rotate to another player,
- do not permit further bids or plays.

When bidding ends in an all-pass redeal:

- phase is `REDEAL`,
- `current_player` is `None`.

### Required tests

Add tests that assert:

- A normal winning play leaves `current_player is None`.
- A bomb that empties the hand leaves `current_player is None`.
- A rocket that empties the hand leaves `current_player is None`.
- A redeal state has `current_player is None`.
- Calling `apply_play` after completion raises and does not mutate state.
- Calling `apply_bid` after completion or redeal raises and does not mutate state.
- Observations of a terminal state do not expose legal actions for any player.

Update any existing tests that expect the winner to remain the current player.

---

## 5. Remove or deprecate ignored `rules` parameters

### Problem

Combination APIs currently accept a `rules` argument but ignore it. This suggests rule-dependent behavior that does not exist.

Silent acceptance of unused configuration is misleading.

### Preferred resolution

Remove the unused `rules` parameter from combination-level APIs when doing so does not create unreasonable compatibility breakage.

Audit at least:

- `Play.from_cards`
- `generate_legal_plays`
- internal classification helpers
- action decoding
- tests
- imports and call sites
- public documentation and docstrings

The strict play-shape rules should remain fixed and canonical.

### Compatibility alternative

If preserving the argument is necessary for an existing public API, deprecate it explicitly:

- Emit `DeprecationWarning`.
- State that combination legality currently uses one fixed strict ruleset.
- Plan removal in a documented future version.
- Do not silently discard the argument.

Example:

```python
import warnings

if rules is not None:
    warnings.warn(
        "The rules argument is deprecated and has no effect; "
        "combination legality uses the fixed strict ruleset.",
        DeprecationWarning,
        stacklevel=2,
    )
```

Do not retain `del rules` as the final implementation.

### Design requirement

Game-level rules may continue to control:

- bidding,
- landlord-card count,
- spring and anti-spring,
- payoff convention.

Combination shape remains fixed unless a future refactor implements true rule-dependent classification and generation end to end.

### Required tests

If removing the parameter:

- Update every call site.
- Verify the public signatures no longer advertise `rules`.
- Run the complete suite.

If deprecating:

- Passing `rules` emits `DeprecationWarning`.
- Omitting `rules` emits no warning.
- Behavior is identical with or without the deprecated argument.
- Documentation identifies the parameter as deprecated.

Choose one approach and apply it consistently. Do not remove the parameter from one public function while silently ignoring it in another.

---

## General implementation requirements

- Inspect the current implementation and tests before editing.
- Make the smallest coherent changes necessary.
- Preserve canonical `Play` behavior.
- Do not introduce new rule variants.
- Use typed exceptions and proper annotations.
- Rejected actions must not partially mutate state.
- Avoid broad exception handling around rule generation.
- Do not mutate caller-owned counters.
- Update package exports and documentation when public signatures change.
- Run the complete test suite after each stage.

---

## Definition of done

This pass is complete only when all of the following are true:

- Actual bomb plays record exactly one `BOMB` event each.
- Actual rocket plays record exactly one `ROCKET` event each.
- Multiple multiplier events preserve order and affect final scoring.
- Invalid multiplier plays leave state unchanged.
- `max_bid < 1` is rejected.
- Bidding `max_bid` ends the auction immediately.
- Zero-count hand entries cannot generate cards.
- Negative hand counts are rejected.
- Finished and redeal states always have `current_player is None`.
- No actions are accepted after terminal states.
- Combination APIs no longer silently ignore a `rules` argument.
- Public signatures, tests, and documentation agree.
- The complete test suite passes.

---

## Completion report

When finished, report:

1. Files changed.
2. Public API changes.
3. Tests added or updated.
4. Exact test command used.
5. Test result.
6. Whether the ignored `rules` parameter was removed or deprecated.
7. Any remaining compatibility concern.

Do not report completion while any listed invariant remains untested.
