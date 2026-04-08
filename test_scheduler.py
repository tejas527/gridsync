import pytest
from unittest.mock import patch, MagicMock
from scheduler import get_mock_carbon_intensity, scale_pods, run_scheduler, DIRTY_REGION, GREEN_REGION

# --- Unit Tests ---

def test_dirty_region_carbon_in_range():
    """Virginia should always return high carbon (300-500)."""
    for _ in range(20):
        value = get_mock_carbon_intensity(DIRTY_REGION)
        assert 300 <= value <= 500

def test_green_region_carbon_in_range():
    """Sweden should always return low carbon (10-50)."""
    for _ in range(20):
        value = get_mock_carbon_intensity(GREEN_REGION)
        assert 10 <= value <= 50

def test_green_is_always_cleaner_than_dirty():
    """Sweden carbon must be lower than Virginia carbon on average."""
    dirty = get_mock_carbon_intensity(DIRTY_REGION)
    green = get_mock_carbon_intensity(GREEN_REGION)
    # Due to random ranges, dirty min (300) > green max (50), so this always holds
    assert dirty > green

# --- Integration Tests (mocked kubectl) ---

@patch("scheduler.subprocess.run")
def test_scale_pods_calls_kubectl(mock_run):
    """scale_pods should invoke kubectl with correct args."""
    mock_run.return_value = MagicMock(returncode=0)
    scale_pods("sweden-green", 3)
    call_args = mock_run.call_args[0][0]
    assert "scale" in call_args
    assert "sweden-green" in call_args
    assert "--replicas=3" in call_args

@patch("scheduler.get_current_pods", return_value=0)
@patch("scheduler.scale_pods")
@patch("scheduler.get_mock_carbon_intensity", side_effect=lambda r: 400 if r == "virginia-dirty" else 20)
def test_migration_triggers_when_dirty_higher(mock_carbon, mock_scale, mock_pods):
    """When Virginia carbon > Sweden carbon, migration should trigger."""
    result = run_scheduler()
    assert result == "migrate"
    # Sweden should be scaled up, Virginia scaled down
    mock_scale.assert_any_call("sweden-green", 3)
    mock_scale.assert_any_call("virginia-dirty", 0)

@patch("scheduler.get_mock_carbon_intensity", side_effect=lambda r: 20 if r == "virginia-dirty" else 400)
def test_no_migration_when_dirty_is_cleaner(mock_carbon):
    """When Virginia carbon < Sweden carbon, no migration should happen."""
    result = run_scheduler()
    assert result == "no_action"
