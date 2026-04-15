# Google Drive Integration Package
# 
# This package handles connecting Google Drive to the VTA.
# Teachers can paste their Drive folder URL, and files can be 
# downloaded and vectorized for the VTA to query.

from . import *

__all__ = [
    'GoogleDriveManager',
    'create_drive_manager',
    'extract_drive_folder_id',
    'extract_drive_file_id',
    'is_drive_url',
    'register_drive_routes',
]