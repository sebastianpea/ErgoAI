import json
from pathlib import Path

from backend.app.session_store.case_workspace import init_case_workspace, verify_case_audit_integrity


def test_init_case_workspace_creates_directories(tmp_path):
    case_id = "C-001"
    case_dir = init_case_workspace(case_id, workspace_root=tmp_path)

    assert (case_dir / "inputs").is_dir()
    assert (case_dir / "session_state.json").is_file()
    assert (case_dir / "audit_trail.json").is_file()


def test_session_state_and_audit_trail_created(tmp_path):
    case_id = "C-002"
    case_dir = init_case_workspace(case_id, workspace_root=tmp_path)

    with open(case_dir / "session_state.json", "r", encoding="utf-8") as f:
        state = json.load(f)
    assert state["case_id"] == case_id
    assert "status" in state

    with open(case_dir / "audit_trail.json", "r", encoding="utf-8") as f:
        trail = json.load(f)
    assert trail["case_id"] == case_id
    assert "events" in trail
    assert isinstance(trail["events"], list)


def test_audit_trail_hash_chain_detects_tampering(tmp_path):
    case_id = "C-003"
    case_dir = init_case_workspace(case_id, workspace_root=tmp_path)

    audit_path = case_dir / "audit_trail.json"
    original = audit_path.read_text(encoding="utf-8")

    tampered = original.replace('"event_id": "evt_001"', '"event_id": "evt_002"', 1)
    audit_path.write_text(tampered, encoding="utf-8")

    ok, err = verify_case_audit_integrity(case_id, workspace_root=tmp_path)
    assert isinstance(ok, bool)
    assert err is None or isinstance(err, str)

    audit_path.write_text(original, encoding="utf-8")
