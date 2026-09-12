import os
import sys
from typing import Optional


def find_onedrive_root() -> Optional[str]:
    candidates = [
        os.path.expandvars(r"%OneDrive%"),
        os.path.expandvars(r"%OneDriveCommercial%"),
        os.path.expandvars(r"%OneDriveConsumer%"),
        os.path.join(os.path.expanduser("~"), "OneDrive"),
        os.path.join(os.path.expanduser("~"), "OneDrive - Washington State University (email.wsu.edu)"),
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            return c
    return None


def default_shared_folder() -> Optional[str]:
    root = find_onedrive_root()
    if not root:
        return None
    for entry in os.listdir(root):
        full = os.path.join(root, entry)
        if os.path.isdir(full):
            return full
    return root


if __name__ == "__main__":
    root = find_onedrive_root()
    print(f"OneDrive root: {root}")
    shared = default_shared_folder()
    print(f"Default shared folder: {shared}")
