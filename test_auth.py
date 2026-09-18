"""Unit tests for the authentication / access-control module (auth.py).

All tests operate on isolated files in tmp_path — they never touch the
real users.json or login_log.csv of the running app.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))

import auth


def _paths(tmp_path):
    return str(tmp_path / "users.json"), str(tmp_path / "login_log.csv")


def test_default_accounts_created_on_first_login(tmp_path):
    uf, _ = _paths(tmp_path)
    profile = auth.verify_credentials("admin", "admin123", users_file=uf)
    assert profile is not None
    assert profile["username"] == "admin"
    assert profile["role"] == "admin"
    stored = json.load(open(uf, encoding="utf-8"))
    assert "admin" in stored and "analyst" in stored


def test_wrong_password_rejected(tmp_path):
    uf, _ = _paths(tmp_path)
    assert auth.verify_credentials("admin", "wrongpass", users_file=uf) is None


def test_unknown_user_rejected(tmp_path):
    uf, _ = _paths(tmp_path)
    assert auth.verify_credentials("nobody", "whatever", users_file=uf) is None


def test_password_never_stored_in_plaintext(tmp_path):
    uf, _ = _paths(tmp_path)
    auth.add_user("bob", "secret99", users_file=uf)
    stored = json.load(open(uf, encoding="utf-8"))
    rec = stored["bob"]
    assert "salt" in rec and "password_hash" in rec
    assert rec["password_hash"] != "secret99"
    assert "secret99" not in str(stored)


def test_same_password_produces_different_hashes(tmp_path):
    uf, _ = _paths(tmp_path)
    auth.add_user("una", "samepass1", users_file=uf)
    auth.add_user("dodo", "samepass1", users_file=uf)
    stored = json.load(open(uf, encoding="utf-8"))
    assert stored["una"]["salt"] != stored["dodo"]["salt"]
    assert stored["una"]["password_hash"] != stored["dodo"]["password_hash"]


def test_add_then_verify(tmp_path):
    uf, _ = _paths(tmp_path)
    assert auth.add_user("carol", "running123", name="Carol", users_file=uf)
    profile = auth.verify_credentials("carol", "running123", users_file=uf)
    assert profile is not None
    assert profile["username"] == "carol"
    assert profile["name"] == "Carol"
    assert profile["role"] == "analyst"


def test_add_duplicate_rejected(tmp_path):
    uf, _ = _paths(tmp_path)
    assert auth.add_user("duke", "password1", users_file=uf)
    assert not auth.add_user("duke", "password2", users_file=uf)


def test_add_rejects_short_password(tmp_path):
    uf, _ = _paths(tmp_path)
    assert not auth.add_user("sam", "123", users_file=uf)


def test_reset_password(tmp_path):
    uf, _ = _paths(tmp_path)
    auth.add_user("eve", "original1", users_file=uf)
    assert auth.reset_password("eve", "changed99", users_file=uf)
    assert auth.verify_credentials("eve", "changed99", users_file=uf) is not None
    assert auth.verify_credentials("eve", "original1", users_file=uf) is None


def test_remove_user(tmp_path):
    uf, _ = _paths(tmp_path)
    auth.add_user("zed", "password1", users_file=uf)
    assert auth.remove_user("zed", users_file=uf)
    assert auth.verify_credentials("zed", "password1", users_file=uf) is None


def test_login_log_records_every_attempt(tmp_path):
    uf, lf = _paths(tmp_path)
    auth.log_login("alice", True, "login successful", login_log=lf)
    auth.log_login("alice", False, "invalid credentials", login_log=lf)
    rows = auth.load_login_log(login_log=lf)
    assert len(rows) == 2, "log must be append-only, one row per attempt"
    assert rows.iloc[0]["success"] == "yes"
    assert rows.iloc[1]["success"] == "no"
    assert rows.iloc[1]["reason"] == "invalid credentials"


QA = [
    ("What was the name of your first pet?", "Rex"),
    ("What city were you born in?", "Lisbon"),
    ("What was your first car?", "Fiat 500"),
]


def test_seed_defaults_include_security_questions(tmp_path):
    """Seeded accounts carry the configured demo questions."""
    uf, _ = _paths(tmp_path)
    auth.verify_credentials("admin", "admin123", users_file=uf)
    assert auth.has_security_questions("admin", users_file=uf)
    assert auth.has_security_questions("analyst", users_file=uf)
    qs = auth.get_security_questions("admin", users_file=uf)
    assert len(qs) == 3


def test_default_demo_answers_verify(tmp_path):
    uf, _ = _paths(tmp_path)
    auth.verify_credentials("admin", "admin123", users_file=uf)
    assert auth.verify_security_answers(
        "admin", ["dog", "mashava", "great zimbabwe"], users_file=uf
    )
    # lenient matching: case-insensitive + trimmed
    assert auth.verify_security_answers(
        "admin", ["  DOG ", "Mashava", "Great Zimbabwe"], users_file=uf
    )


def test_set_security_questions(tmp_path):
    uf, _ = _paths(tmp_path)
    auth.add_user("mike", "password1", users_file=uf)
    assert auth.set_security_questions("mike", QA, users_file=uf)
    assert auth.has_security_questions("mike", users_file=uf)
    assert auth.get_security_questions("mike", users_file=uf)[0] == QA[0][0]


def test_set_security_questions_requires_exactly_three(tmp_path):
    uf, _ = _paths(tmp_path)
    auth.add_user("nina", "password1", users_file=uf)
    assert not auth.set_security_questions("nina", QA[:2], users_file=uf)
    assert not auth.set_security_questions("nina", QA[:1], users_file=uf)
    assert auth.set_security_questions("nina", QA, users_file=uf)


def test_verify_security_answers_case_insensitive(tmp_path):
    uf, _ = _paths(tmp_path)
    auth.add_user("oscar", "password1", users_file=uf)
    auth.set_security_questions("oscar", QA, users_file=uf)
    assert auth.verify_security_answers(
        "oscar", ["  rex ", "LISBON", "fiat 500"], users_file=uf
    )


def test_verify_security_answers_wrong(tmp_path):
    uf, _ = _paths(tmp_path)
    auth.add_user("pam", "password1", users_file=uf)
    auth.set_security_questions("pam", QA, users_file=uf)
    assert not auth.verify_security_answers(
        "pam", ["Rex", "Tokyo", "Fiat 500"], users_file=uf
    )


def test_verify_security_answers_without_questions(tmp_path):
    uf, _ = _paths(tmp_path)
    auth.add_user("quinn", "password1", users_file=uf)
    assert not auth.verify_security_answers(
        "quinn", ["a", "b", "c"], users_file=uf
    )


def test_answer_hashes_never_plaintext(tmp_path):
    uf, _ = _paths(tmp_path)
    auth.add_user("ria", "password1", users_file=uf)
    auth.set_security_questions("ria", QA, users_file=uf)
    stored = json.load(open(uf, encoding="utf-8"))
    rec = stored["ria"]["security_questions"][0]
    assert "answer_hash" in rec and "salt" in rec
    assert rec["answer_hash"] != "Rex"
    assert "Rex" not in str(stored)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])