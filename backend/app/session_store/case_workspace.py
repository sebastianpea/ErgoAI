from pathlib import Path

from backend.app.session_store.audit_file_manager import AuditFileManager


CASE_WORKSPACE_ROOT = Path("casos_jabil_workspace")


def init_case_workspace(case_id: str, workspace_root: Path | None = None) -> Path:
    root = workspace_root or CASE_WORKSPACE_ROOT
    mgr = AuditFileManager(workspace_root=root)
    return mgr.init_case_workspace(case_id)


def verify_case_audit_integrity(
    case_id: str, workspace_root: Path | None = None
) -> tuple[bool, str | None]:
    root = workspace_root or CASE_WORKSPACE_ROOT
    mgr = AuditFileManager(workspace_root=root)
    return mgr.verify_case_audit_integrity(case_id)
