from common.broadcast_protocol import DoctorStatusPayload, TokenUpdatePayload
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


def test_chime_only_for_a_new_call():
    state = DisplayState()
    waiting = TokenUpdatePayload(token_id="t1", token_num=1, dept_id=1, status="WAITING")
    called = TokenUpdatePayload(token_id="t1", token_num=1, dept_id=1, status="CALLED")
    assert state.is_new_call(waiting) is False
    state.apply(waiting)
    assert state.is_new_call(called) is True
    state.apply(called)
    assert state.is_new_call(called) is False  # duplicate packet: stay silent


def test_doctors_are_tracked_latest_status_by_name():
    state = DisplayState()
    state.apply_doctor(DoctorStatusPayload("d2", "Dr. Vikram Shah", 1, "AVAILABLE"))
    state.apply_doctor(DoctorStatusPayload("d1", "Dr. Asha Rao", 1, "AVAILABLE"))
    state.apply_doctor(DoctorStatusPayload("d1", "Dr. Asha Rao", 1, "OFF_DUTY"))

    assert [row.text for row in state.doctors()] == [
        "Dr. Asha Rao: Off duty",
        "Dr. Vikram Shah: Available",
    ]
