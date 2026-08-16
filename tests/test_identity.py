from app.db.models import Patient
from app.services.linking.identity import identity_warnings, target_identity_compatible


def _aarav() -> Patient:
    return Patient(
        canonical_name="Aarav Sharma",
        normalized_name="aarav sharma",
        username="aarav",
        phone="9876543210",
        normalized_phone="9876543210",
        date_of_birth="1988-03-14",
    )


def test_rejects_different_person_without_phone():
    ok, reason = target_identity_compatible("Priya Nair", None, "1992-06-20", _aarav())
    assert not ok
    assert "does not match" in reason or "name score" in reason


def test_rejects_missing_identity():
    ok, reason = target_identity_compatible(None, None, None, _aarav())
    assert not ok
    assert "name or phone" in reason


def test_rejects_different_phone():
    ok, _ = target_identity_compatible("Aarav Sharma", "1111111111", "1988-03-14", _aarav())
    assert not ok


def test_accepts_same_phone():
    ok, _ = target_identity_compatible("Aarav Sharma", "98765 43210", "1988-03-14", _aarav())
    assert ok


def test_accepts_fuzzy_name_when_phone_absent():
    priya = Patient(
        canonical_name="Priya Nair",
        normalized_name="priya nair",
        phone=None,
        date_of_birth="1992-06-20",
    )
    ok, _ = target_identity_compatible("Priya Nair", None, "1992-06-20", priya)
    assert ok


def test_warnings_for_missing_and_different_identity():
    empty = Patient(canonical_name=None, username="newuser", phone=None)
    missing = identity_warnings(None, None, None, empty)
    assert any("name" in w.lower() for w in missing)
    assert any("phone" in w.lower() for w in missing)
    assert not any("patient id" in w.lower() for w in missing)

    aarav = _aarav()
    slight = identity_warnings("Aarav S Sharma", "9876543210", "1988-03-14", aarav)
    assert any("slightly different" in w or "does not match" in w for w in slight)

    different = identity_warnings("Priya Nair", "1111111111", "1992-06-20", aarav)
    assert any("does not match" in w for w in different)
    assert any("phone" in w.lower() for w in different)
