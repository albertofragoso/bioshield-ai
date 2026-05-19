from app.core.context import REQUEST_ID_VAR


def test_request_id_var_default_is_none():
    assert REQUEST_ID_VAR.get() is None


def test_request_id_var_set_and_get():
    token = REQUEST_ID_VAR.set("abc-123")
    assert REQUEST_ID_VAR.get() == "abc-123"
    REQUEST_ID_VAR.reset(token)
    assert REQUEST_ID_VAR.get() is None
