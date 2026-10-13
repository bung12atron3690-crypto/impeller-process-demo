from math import pi

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import analysis_store, main
from app.planning import PlanRequest, generate_plan
from test_features import candidate


def inputs(analysis_id="test", **changes):
    values = dict(analysis_id=analysis_id, confirmed_open_impeller=True, confirmed_cutting_inputs=True,
                  material="6061-T6", machine_axes=5, spindle_max_rpm=12000,
                  machine_diameter_limit_mm=200, machine_height_limit_mm=100,
                  blank_diameter_mm=130, blank_height_mm=36, confirmed_channel_width_mm=25,
                  confirmed_root_radius_mm=4, confirmed_min_wall_mm=3,
                  cutting_speed_m_min=120, feed_per_tooth_mm=0.03, flutes=3, machine_rate_per_hour=300)
    values.update(changes)
    return PlanRequest(**values)


def test_formula_and_provenance(candidate):
    plan = generate_plan(candidate, inputs())
    assert plan["status"] == "review_required"
    assert plan["executable_nc"] is False
    assert plan["tools"][0]["diameter_mm"] == 12
    assert plan["tools"][1]["diameter_mm"] == 8
    parameters = plan["steps"][1]["parameters"]
    assert parameters["rpm"] == int(1000*120/(pi*12))
    assert parameters["feed_mm_min"] == pytest.approx(parameters["rpm"]*3*0.03)
    removed = pi*130**2/4*36-candidate.volume_mm3
    expected = removed / (parameters["feed_mm_min"]*parameters["ap_mm"]*parameters["ae_mm"])
    assert plan["estimate"]["ideal_roughing_minutes"] == pytest.approx(expected)
    assert plan["estimate"]["ideal_roughing_cost"] == pytest.approx(expected/60*300)
    assert plan["estimate"]["total_minutes"] is None


def test_spindle_limit_recalculates_feed(candidate):
    p=generate_plan(candidate,inputs(spindle_max_rpm=1000))["steps"][1]["parameters"]
    assert p["rpm"] == 1000
    assert p["feed_mm_min"] == 90
    assert p["achieved_vc_m_min"] < p["requested_vc_m_min"]
    assert p["rpm_limited"]


def test_confirmed_gap_not_sampled_arc_drives_tool(candidate):
    wide=generate_plan(candidate,inputs(confirmed_channel_width_mm=30))
    narrow=generate_plan(candidate,inputs(confirmed_channel_width_mm=10))
    assert wide["tools"][0]["diameter_mm"] == 16
    assert narrow["tools"][0]["diameter_mm"] == 6
    assert narrow["status"] == "blocked"  # insufficient demo flute length
    assert narrow["estimate"]["ideal_roughing_minutes"] is None


@pytest.mark.parametrize("changes", [{"machine_axes":3},{"machine_diameter_limit_mm":100},{"confirmed_channel_width_mm":1}])
def test_machine_and_tool_blockers(candidate,changes):
    plan=generate_plan(candidate,inputs(**changes))
    assert plan["status"] == "blocked"
    assert plan["blockers"]
    assert plan["estimate"]["ideal_roughing_minutes"] is None


def test_missing_root_radius_keeps_finishing_pending(candidate):
    plan=generate_plan(candidate,inputs(confirmed_root_radius_mm=None))
    assert len(plan["tools"]) == 1
    assert plan["steps"][2]["parameters"] is None
    assert plan["warnings"]


def test_thin_wall_reduces_engagement(candidate):
    regular=generate_plan(candidate,inputs())["steps"][1]["parameters"]
    thin=generate_plan(candidate,inputs(confirmed_min_wall_mm=2))["steps"][1]["parameters"]
    assert thin["ap_mm"] == regular["ap_mm"]/2
    assert thin["ae_mm"] == regular["ae_mm"]/2


@pytest.mark.parametrize("changes", [{"blank_diameter_mm":100},{"confirmed_open_impeller":False},{"confirmed_cutting_inputs":False},{"confirmed_channel_width_mm":130}])
def test_invalid_context_does_not_generate(candidate,changes):
    with pytest.raises(ValueError): generate_plan(candidate,inputs(**changes))


@pytest.mark.parametrize("changes", [{"feed_per_tooth_mm":0},{"spindle_max_rpm":float('nan')},{"blank_height_mm":float('inf')},{"confirmed_open_impeller":"yes"}])
def test_validation_rejects_bad_inputs(changes):
    with pytest.raises(ValidationError): inputs(**changes)


def test_non_candidate_cannot_use_template(candidate):
    not_impeller=candidate.model_copy(update={"impeller":{"status":"unresolved"}})
    with pytest.raises(ValueError): generate_plan(not_impeller,inputs())


def test_endpoint_uses_cached_geometry_and_rejects_forgery(candidate):
    client=TestClient(main.app)
    saved=candidate.model_copy(deep=True)
    analysis_store.save(saved)
    request=inputs(saved.analysis_id).model_dump()
    assert client.post('/api/process-plan',json=request).status_code == 200
    request['analysis']={'impeller':{'status':'candidate'}}
    assert client.post('/api/process-plan',json=request).status_code == 422
    assert client.post('/api/process-plan',json=inputs('unknown').model_dump()).status_code == 404


def test_metadata_cache_bounded_and_expiring(candidate,monkeypatch):
    monkeypatch.setattr(analysis_store,'MAX_ENTRIES',2)
    keys=[analysis_store.save(candidate.model_copy(deep=True)) for _ in range(3)]
    assert analysis_store.get(keys[0]) is None
    assert analysis_store.get(keys[-1]).preview is None
    monkeypatch.setattr(analysis_store,'TTL_SECONDS',-1)
    assert analysis_store.get(keys[-1]) is None
