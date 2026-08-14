from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Iterable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}


def extract_folder_id(value: str) -> str:
    value = value.strip()
    match = re.search(r"/folders/([A-Za-z0-9_-]+)", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", value):
        return value
    raise ValueError(f"Google Drive folder URL/ID を認識できません: {value}")


def _default_token_path() -> Path:
    root = Path(os.getenv("APPDATA") or Path.home() / ".config") / "RooomPhotoSkills"
    root.mkdir(parents=True, exist_ok=True)
    return root / "token.json"


def get_drive_service(credentials_file: str | None = None, token_file: str | None = None):
    credentials_file = credentials_file or os.getenv("GOOGLE_OAUTH_CLIENT_FILE") or "credentials.json"
    token_path = Path(token_file) if token_file else _default_token_path()
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not Path(credentials_file).exists():
            raise FileNotFoundError(
                "Google OAuth credentials.json がありません。--credentials で指定するか "
                "GOOGLE_OAUTH_CLIENT_FILE を設定してください。"
            )
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_images(service, folder_id: str) -> list[dict]:
    items: list[dict] = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken,files(id,name,mimeType,size,createdTime,modifiedTime,parents)",
                pageSize=1000,
                pageToken=page_token,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )
        items.extend(f for f in response.get("files", []) if f.get("mimeType") in IMAGE_MIMES)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return items


def download_file(service, file_id: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with destination.open("wb") as file_handle:
        downloader = MediaIoBaseDownload(file_handle, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return destination


def find_or_create_folder(service, parent_id: str, name: str) -> str:
    safe_name = name.replace("'", "\\'")
    query = (
        f"'{parent_id}' in parents and trashed = false and "
        f"mimeType = 'application/vnd.google-apps.folder' and name = '{safe_name}'"
    )
    response = (
        service.files()
        .list(
            q=query,
            fields="files(id,name)",
            pageSize=10,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        )
        .execute()
    )
    files = response.get("files", [])
    if files:
        return files[0]["id"]
    metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    created = service.files().create(body=metadata, fields="id", supportsAllDrives=True).execute()
    return created["id"]


def upload_bytes(service, parent_id: str, name: str, data: bytes, mime_type: str) -> str:
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type, resumable=True)
    metadata = {"name": name, "parents": [parent_id]}
    created = (
        service.files()
        .create(body=metadata, media_body=media, fields="id", supportsAllDrives=True)
        .execute()
    )
    return created["id"]


def upload_text(service, parent_id: str, name: str, text: str, mime_type: str = "text/plain") -> str:
    return upload_bytes(service, parent_id, name, text.encode("utf-8-sig"), mime_type)


def ensure_output_tree(service, source_folder_id: str, output_name: str, platform_names: Iterable[str]) -> dict[str, str]:
    root = find_or_create_folder(service, source_folder_id, output_name)
    result = {"root": root}
    for name in platform_names:
        result[name] = find_or_create_folder(service, root, name)
    return result
