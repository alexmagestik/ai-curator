from app.auth.passwords import hash_password, verify_password


def test_hash_and_verify_password() -> None:
    password = "secret123"
    password_hash = hash_password(password)
    assert verify_password(password, password_hash)
    assert not verify_password("wrong", password_hash)


def test_hash_password_is_unique() -> None:
    first = hash_password("same")
    second = hash_password("same")
    assert first != second
