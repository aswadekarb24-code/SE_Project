import pytest

from common.broadcast_protocol import (
    DoctorStatusPayload,
    PacketDecodeError,
    TokenUpdatePayload,
    decode_packet,
)


def test_encode_decode_round_trip():
    payload = TokenUpdatePayload(token_id="t1", token_num=5, dept_id=2, status="WAITING")
    decoded = TokenUpdatePayload.decode(payload.encode())
    assert decoded == payload


def test_decode_rejects_invalid_json():
    with pytest.raises(PacketDecodeError):
        TokenUpdatePayload.decode(b"not json at all")


def test_decode_rejects_non_object_json():
    with pytest.raises(PacketDecodeError):
        TokenUpdatePayload.decode(b"[1, 2, 3]")


def test_decode_rejects_missing_fields():
    with pytest.raises(PacketDecodeError):
        TokenUpdatePayload.decode(b'{"token_id": "t1"}')


def test_decode_rejects_non_numeric_token_num():
    with pytest.raises(PacketDecodeError):
        TokenUpdatePayload.decode(
            b'{"token_id": "t1", "token_num": "not-a-number", "dept_id": 1, "status": "WAITING"}'
        )


def test_token_packets_are_tagged_and_legacy_untagged_ones_still_decode():
    payload = TokenUpdatePayload(token_id="t1", token_num=5, dept_id=2, status="WAITING")
    assert b'"kind": "token"' in payload.encode()
    legacy = b'{"token_id": "t1", "token_num": 5, "dept_id": 2, "status": "WAITING"}'
    assert decode_packet(legacy) == payload


def test_doctor_status_round_trip_and_dispatch():
    payload = DoctorStatusPayload(doctor_id="d1", name="Dr. Asha Rao", dept_id=1, status="BUSY")
    assert DoctorStatusPayload.decode(payload.encode()) == payload
    assert decode_packet(payload.encode()) == payload


def test_each_decoder_rejects_the_other_kind():
    doctor = DoctorStatusPayload(doctor_id="d1", name="Dr. X", dept_id=1, status="BUSY")
    token = TokenUpdatePayload(token_id="t1", token_num=1, dept_id=1, status="WAITING")
    with pytest.raises(PacketDecodeError):
        TokenUpdatePayload.decode(doctor.encode())
    with pytest.raises(PacketDecodeError):
        DoctorStatusPayload.decode(token.encode())


def test_decode_packet_rejects_garbage():
    with pytest.raises(PacketDecodeError):
        decode_packet(b"\xff\xfe not json")
    with pytest.raises(PacketDecodeError):
        decode_packet(b'{"kind": "doctor", "doctor_id": "d1"}')
