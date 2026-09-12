import os
import io
import json
import time
import requests
from typing import List, Dict, Optional

import msal

SHAREPOINT_TENANT = os.getenv("SHAREPOINT_TENANT", "emailwsu-my.sharepoint.com")
SHAREPOINT_SITE_PATH = os.getenv("SHAREPOINT_SITE_PATH", "/sites/Shared")
SHAREPOINT_DRIVE_NAME = os.getenv("SHAREPOINT_DRIVE_NAME", "Documents")

CLIENT_ID = os.getenv("SHAREPOINT_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SHAREPOINT_CLIENT_SECRET", "")
USERNAME = os.getenv("SHAREPOINT_USERNAME", "")
PASSWORD = os.getenv("SHAREPOINT_PASSWORD", "")
TENANT_ID = os.getenv("SHAREPOINT_TENANT_ID", "common")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

SHAREPOINT_API_BASE = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_TENANT}:{SHAREPOINT_SITE_PATH}"

TOKEN_CACHE_FILE = os.getenv("SHAREPOINT_TOKEN_CACHE", ".sharepoint_token_cache.json")


def _build_app():
    if CLIENT_SECRET:
        return msal.ConfidentialClientApplication(
            CLIENT_ID,
            authority=AUTHORITY,
            client_credential=CLIENT_SECRET,
        )
    return msal.PublicClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
    )


def _load_cache():
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            cache.deserialize(f.read())
    return cache


def _save_cache(cache):
    if cache.has_state_changed:
        with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(cache.serialize())


def _get_access_token() -> str:
    if not CLIENT_ID:
        raise ValueError(
            "SHAREPOINT_CLIENT_ID is required. Set it in your .env. "
            "Also configure SHAREPOINT_USERNAME or SHAREPOINT_CLIENT_SECRET."
        )

    app = _build_app()
    cache = _load_cache()

    scopes = ["Sites.Read.All", "User.Read"]

    accounts = app.get_accounts(username=USERNAME or None)

    result = app.acquire_token_silent(scopes=scopes, account=accounts[0] if accounts else None)

    if not result:
        if CLIENT_SECRET and not USERNAME:
            raise RuntimeError(
                "App-only token acquisition failed or is blocked by Conditional Access. "
                "If your tenant blocks client-secret auth, use device-code flow: "
                "set SHAREPOINT_USERNAME and omit CLIENT_SECRET."
            )

        result = app.acquire_token_by_device_flow(scopes=scopes)

        if "access_token" not in result:
            raise RuntimeError(f"SharePoint auth failed: {result.get('error_description')}")

    _save_cache(cache)
    return result["access_token"]


def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def _get_drive_id(token: str) -> str:
    url = f"{SHAREPOINT_API_BASE}/drives"
    resp = requests.get(url, headers=_headers(token), timeout=30)
    resp.raise_for_status()
    drives = resp.json().get("value", [])
    for drive in drives:
        if drive.get("name", "").lower() in (
            SHAREPOINT_DRIVE_NAME.lower(),
            "shared documents",
            "documents",
        ):
            return drive["id"]
    if drives:
        return drives[0]["id"]
    raise RuntimeError("No drives found on SharePoint site.")


def _list_children(token: str, drive_id: str, folder_id: Optional[str] = None) -> List[Dict]:
    if folder_id:
        url = f"{SHAREPOINT_API_BASE}/drives/{drive_id}/items/{folder_id}/children"
    else:
        url = f"{SHAREPOINT_API_BASE}/drives/{drive_id}/root/children"

    results: List[Dict] = []
    while url:
        resp = requests.get(url, headers=_headers(token), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
        time.sleep(0.1)
    return results


def _get_item_content(token: str, drive_id: str, item_id: str, mime_type: str) -> bytes:
    url = f"{SHAREPOINT_API_BASE}/drives/{drive_id}/items/{item_id}/content"
    resp = requests.get(url, headers=_headers(token), timeout=60, allow_redirects=True)
    resp.raise_for_status()
    return resp.content


def get_sharepoint_service() -> Dict:
    token = _get_access_token()
    drive_id = _get_drive_id(token)
    return {
        "access_token": token,
        "drive_id": drive_id,
        "site_path": SHAREPOINT_SITE_PATH,
    }


def list_sharepoint_files(
    service: Dict,
    folder_id: Optional[str] = None,
    mime_types: Optional[List[str]] = None,
) -> List[Dict]:
    token = service["access_token"]
    drive_id = service["drive_id"]

    allowed_extensions = set()
    if mime_types:
        ext_map = {
            "application/pdf": ".pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
            "text/plain": ".txt",
            "text/markdown": ".md",
            "text/html": ".html",
            "text/csv": ".csv",
        }
        for mt in mime_types:
            allowed_extensions.add(ext_map.get(mt, ""))

    items = _list_children(token, drive_id, folder_id)

    files: List[Dict] = []
    for item in items:
        if item.get("folder"):
            continue

        name = item.get("name", "")
        ext = os.path.splitext(name)[1].lower()
        if allowed_extensions and ext not in allowed_extensions:
            continue

        mime = item.get("file", {}).get("mimeType", "application/octet-stream")

        files.append({
            "id": item["id"],
            "name": name,
            "mimeType": mime,
            "size": item.get("size"),
            "modifiedTime": item.get("lastModifiedDateTime"),
        })

    return files


def download_file(service: Dict, file_id: str) -> bytes:
    token = service["access_token"]
    drive_id = service["drive_id"]
    return _get_item_content(token, drive_id, file_id, "")


def get_file_content(service: Dict, file_id: str, mime_type: str) -> bytes:
    return download_file(service, file_id)
