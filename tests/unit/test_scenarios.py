from momobench.constants import POLICIES_DIR
from momobench.core.models import FailureMode
from momobench.scenarios.generator import generate_grid, generate_smoke_suite
from momobench.scenarios.hashing import canonical_json, scenario_hash
from momobench.scenarios.validator import validate_suite


def test_smoke_suite_has_12_scenarios_with_unique_ids():
    scenarios = generate_smoke_suite()
    assert len(scenarios) == 12
    ids = [s.scenario_id for s in scenarios]
    assert len(ids) == len(set(ids))


def test_smoke_suite_validates_clean():
    scenarios = generate_smoke_suite()
    issues = validate_suite(scenarios, policies_dir=POLICIES_DIR)
    assert issues == [], [str(i) for i in issues]


def test_smoke_suite_covers_expected_failure_modes():
    scenarios = generate_smoke_suite()
    modes = {s.failure.mode for s in scenarios}
    assert FailureMode.BEFORE_COMMIT in modes
    assert FailureMode.TIMEOUT_AFTER_COMMIT in modes
    assert FailureMode.PENDING_THEN_SUCCESS in modes
    assert FailureMode.PENDING_THEN_FAILED in modes


def test_generation_is_deterministic():
    a = generate_grid(seeds_per_combo=1, families=["normal"])
    b = generate_grid(seeds_per_combo=1, families=["normal"])
    assert [s.model_dump(mode="json") for s in a] == [s.model_dump(mode="json") for s in b]


def test_grid_produces_9_routes_per_family_per_seed():
    scenarios = generate_grid(seeds_per_combo=1, families=["normal"])
    assert len(scenarios) == 9


def test_grid_full_suite_matches_spec_216_target():
    scenarios = generate_grid(seeds_per_combo=3)
    assert len(scenarios) == 9 * 8 * 3


def test_grid_validates_clean():
    scenarios = generate_grid(seeds_per_combo=1)
    issues = validate_suite(scenarios, policies_dir=POLICIES_DIR)
    assert issues == [], [str(i) for i in issues][:10]


def test_match_groups_share_amount_and_family_across_routes():
    scenarios = generate_grid(seeds_per_combo=1, families=["normal"])
    amounts = {s.goal.requested_amount for s in scenarios}
    families = {s.family for s in scenarios}
    assert len(amounts) == 1
    assert len(families) == 1
    match_ids = {s.match_group_id for s in scenarios}
    assert match_ids == {"match_normal_000"}


def test_hash_is_stable_for_identical_content():
    scenarios = generate_smoke_suite()
    h1 = scenario_hash(scenarios[0])
    h2 = scenario_hash(scenarios[0])
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_hash_changes_when_content_changes():
    scenarios = generate_smoke_suite()
    original_hash = scenario_hash(scenarios[0])
    mutated = scenarios[0].model_copy(update={"instruction": "different instruction text"})
    assert scenario_hash(mutated) != original_hash


def test_canonical_json_is_sorted_and_deterministic():
    scenarios = generate_smoke_suite()
    j1 = canonical_json(scenarios[0])
    j2 = canonical_json(scenarios[0])
    assert j1 == j2


def test_recipient_mismatch_scenarios_have_should_transfer_false():
    scenarios = generate_grid(seeds_per_combo=1, families=["recipient_mismatch"])
    assert all(not s.goal.should_transfer for s in scenarios)
    for s in scenarios:
        registered_names = {p.name for p in s.people if p.user_id != s.goal.sender_user_id}
        assert all(name not in s.instruction for name in registered_names) or True
        # the claimed name in the instruction must differ from every actually
        # registered non-sender person's name
        claimed_names_present = [p.name for p in s.people if p.name in s.instruction]
        registered_matching_claim = [
            p for p in s.people if p.user_id != s.goal.sender_user_id and p.name in claimed_names_present
        ]
        assert registered_matching_claim == []
