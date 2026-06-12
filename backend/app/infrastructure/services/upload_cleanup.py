import os
import shutil
import uuid


def _resolve_upload_path(upload_dir: str, public_url: str) -> tuple[str, str] | None:
    if not public_url.startswith("/uploads/"):
        return None
    relative = public_url[len("/uploads/") :].lstrip("/")
    if not relative or ".." in relative.replace("\\", "/").split("/"):
        return None
    return relative, os.path.join(upload_dir, relative)


def delete_uploaded_file(upload_dir: str, public_url: str | None) -> None:
    if not public_url:
        return
    resolved = _resolve_upload_path(upload_dir, public_url)
    if not resolved:
        return
    _, path = resolved
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def copy_uploaded_file(upload_dir: str, public_url: str | None) -> str | None:
    if not public_url:
        return None
    resolved = _resolve_upload_path(upload_dir, public_url)
    if not resolved:
        return None
    relative, source_path = resolved
    if not os.path.isfile(source_path):
        return None
    dest_relative = f"{uuid.uuid4()}{os.path.splitext(relative)[1] or '.jpg'}"
    dest_path = os.path.join(upload_dir, dest_relative)
    try:
        os.makedirs(upload_dir, exist_ok=True)
        shutil.copy2(source_path, dest_path)
    except OSError:
        return None
    return f"/uploads/{dest_relative.replace(os.sep, '/')}"