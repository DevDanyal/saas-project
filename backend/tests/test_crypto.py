from app.services import crypto


def test_encrypt_roundtrip():
    token = crypto.encrypt_text("very-secret-token")
    assert token.startswith("gAAAAA")
    assert crypto.decrypt_text(token) == "very-secret-token"


def test_decrypt_legacy_plaintext():
    assert crypto.decrypt_text("not-yet-encrypted") == "not-yet-encrypted"


def test_empty_values():
    assert crypto.encrypt_text("") == ""
    assert crypto.decrypt_text("") == ""