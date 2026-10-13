from common.broadcast_protocol import TokenUpdatePayload
from display_sim.display_state import DisplayState


def test_apply_tracks_latest_status_per_token():
    state = DisplayState()
    state.apply(TokenUpdatePayload(token_id="t1", token_num=1, dept_id=1, status="WAITING"))
    state.apply(TokenUpdatePayload(token_id="t1", token_num=1, dept_id=1, status="CALLED"))

    rows = state.rows_for_department(1)
    assert len(rows) == 1
    assert rows[0].status == "CALLED"
    assert rows[0].text == "Dept 1 - Token #1: CALLED"


def test_rows_for_department_filters_other_departments():
    state = DisplayState()
    state.apply(TokenUpdatePayload(token_id="t1", token_num=1, dept_id=1, status="WAITING"))
    state.apply(TokenUpdatePayload(token_id="t2", token_num=1, dept_id=2, status="WAITING"))

    assert len(state.rows_for_department(1)) == 1
    assert len(state.rows_for_department(2)) == 1
    assert len(state.all_rows()) == 2


def test_apply_distinct_tokens_do_not_overwrite_each_other():
    state = DisplayState()
    state.apply(TokenUpdatePayload(token_id="t1", token_num=1, dept_id=1, status="WAITING"))
    state.apply(TokenUpdatePayload(token_id="t2", token_num=2, dept_id=1, status="WAITING"))

    assert len(state.rows_for_department(1)) == 2
