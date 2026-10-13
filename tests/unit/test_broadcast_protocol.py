import pytest

from common.broadcast_protocol import PacketDecodeError, TokenUpdatePayload


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
