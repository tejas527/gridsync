import pytest
from unittest.mock import patch, MagicMock, mock_open
from scheduler import get_mock_carbon_intensity, scale_pods, run_scheduler, DIRTY_REGION, GREEN_REGION

# ── Shared mock for regions.yaml ───────────────────────────────────────────────
MOCK_REGIONS = {
    "regions": [
        {"name": "virginia-dirty", "display": "Virginia (US-East)", "namespace": "virginia-dirty", "carbon_profile": "high"},
        {"name": "ireland-mixed",  "display": "Ireland (EU-West)",   "namespace": "ireland-mixed",  "carbon_profile": "medium"},
        {"name": "sweden-green",   "display": "Sweden (EU-North)",   "namespace": "sweden-green",   "carbon_profile": "low"},
    ]
}


# ── Unit Tests: Carbon Intensity Ranges ───────────────────────────────────────

def test_dirty_region_carbon_in_range():
    """Virginia (high profile) should always return 300–500 gCO2/kWh."""
    for _ in range(30):
        value = get_mock_carbon_intensity(DIRTY_REGION)
        assert 300 <= value <= 500, f"Got {value}, expected 300–500"


def test_green_region_carbon_in_range():
    """Sweden (low profile) should always return 10–50 gCO2/kWh."""
    for _ in range(30):
        value = get_mock_carbon_intensity(GREEN_REGION)
        assert 10 <= value <= 50, f"Got {value}, expected 10–50"


def test_medium_profile_carbon_in_range():
    """Ireland (medium profile) should always return 100–250 gCO2/kWh."""
    for _ in range(30):
        value = get_mock_carbon_intensity("ireland-mixed")
        assert 100 <= value <= 250, f"Got {value}, expected 100–250"


def test_green_is_always_cleaner_than_dirty():
    """Sweden max (50) is always less than Virginia min (300) — ranges never overlap."""
    dirty = get_mock_carbon_intensity(DIRTY_REGION)
    green = get_mock_carbon_intensity(GREEN_REGION)
    assert dirty > green


# ── Unit Tests: scale_pods ────────────────────────────────────────────────────

@patch("scheduler.subprocess.run")
def test_scale_pods_calls_kubectl(mock_run):
    """scale_pods should invoke kubectl with the correct arguments."""
    mock_run.return_value = MagicMock(returncode=0)
    scale_pods("sweden-green", 3)
    call_args = mock_run.call_args[0][0]
    assert "scale" in call_args
    assert "sweden-green" in call_args
    assert "--replicas=3" in call_args


@patch("scheduler.subprocess.run")
def test_scale_pods_zero_replicas(mock_run):
    """scale_pods should correctly pass --replicas=0 when draining."""
    mock_run.return_value = MagicMock(returncode=0)
    scale_pods("virginia-dirty", 0)
    call_args = mock_run.call_args[0][0]
    assert "--replicas=0" in call_args
    assert "virginia-dirty" in call_args


# ── Integration Tests: run_scheduler (N-region logic) ─────────────────────────

@patch("scheduler.load_regions", return_value=MOCK_REGIONS["regions"])
@patch("scheduler.ensure_namespace")
@patch("scheduler.get_current_pods", return_value=0)
@patch("scheduler.scale_pods")
@patch("scheduler.get_mock_carbon_intensity", side_effect=lambda r: {"virginia-dirty": 450, "ireland-mixed": 160, "sweden-green": 25}[r])
def test_migration_to_greenest_region(mock_carbon, mock_scale, mock_pods, mock_ensure, mock_regions):
    """Scheduler should migrate to the namespace with the lowest carbon intensity."""
    result = run_scheduler()
    assert result == "migrate"
    # Sweden (25 gCO2) should be scaled UP
    mock_scale.assert_any_call("sweden-green", 3)
    # Virginia and Ireland should be scaled DOWN
    mock_scale.assert_any_call("virginia-dirty", 0)
    mock_scale.assert_any_call("ireland-mixed", 0)


@patch("scheduler.load_regions", return_value=MOCK_REGIONS["regions"])
@patch("scheduler.get_current_pods", return_value=3)   # already 3 pods in greenest region
@patch("scheduler.scale_pods")
@patch("scheduler.get_mock_carbon_intensity", side_effect=lambda r: {"virginia-dirty": 450, "ireland-mixed": 160, "sweden-green": 25}[r])
def test_no_action_when_already_optimal(mock_carbon, mock_scale, mock_pods, mock_regions):
    """When the greenest region already has pods, no migration should occur."""
    result = run_scheduler()
    assert result == "no_action"
    mock_scale.assert_not_called()


@patch("scheduler.load_regions", return_value=MOCK_REGIONS["regions"])
@patch("scheduler.ensure_namespace")
@patch("scheduler.get_current_pods", return_value=0)
@patch("scheduler.scale_pods")
@patch("scheduler.get_mock_carbon_intensity", side_effect=lambda r: {"virginia-dirty": 110, "ireland-mixed": 450, "sweden-green": 300}[r])
def test_migration_picks_lowest_not_hardcoded(mock_carbon, mock_scale, mock_pods, mock_ensure, mock_regions):
    """When Virginia is unexpectedly the greenest, it should be the migration target."""
    result = run_scheduler()
    assert result == "migrate"
    # Virginia is greenest at 110 — scheduler should scale it UP
    mock_scale.assert_any_call("virginia-dirty", 3)
    # Others should be scaled DOWN
    mock_scale.assert_any_call("ireland-mixed", 0)
    mock_scale.assert_any_call("sweden-green", 0)
