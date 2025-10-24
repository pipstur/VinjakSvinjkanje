from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.service_account import Credentials
import io
import os
import time

# ---- CONFIG ----
FOLDER_ID = "1ltg4H_-mMOJRh6ZuXBCnC_6ebaKFZEQP"
LOCAL_DIR = "slike/unedited"
POLL_INTERVAL = 60  # seconds

# ---- AUTH ----
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
service = build("drive", "v3", credentials=creds)


# ---- DOWNLOAD FILES ----
def download_files():
    # Dohvati listu fajlova sa Drive-a
    results = (
        service.files()
        .list(q=f"'{FOLDER_ID}' in parents and trashed=false", fields="files(id, name, mimeType)")
        .execute()
    )
    drive_files = results.get("files", [])

    # Prebroj fajlove u lokalnom folderu
    local_files = [f for f in os.listdir(LOCAL_DIR) if os.path.isfile(os.path.join(LOCAL_DIR, f))]

    # Ako se broj fajlova poklapa, ne skidaj ništa
    if len(drive_files) == len(local_files):
        print("Broj fajlova na Drive-u i lokalno se poklapa. Nema potrebe za download.")
        return

    # Inače, skidaj samo fajlove koji ne postoje lokalno
    for file in drive_files:
        file_id = file["id"]
        file_name = file["name"]
        local_path = os.path.join(LOCAL_DIR, file_name)

        if os.path.exists(local_path):
            continue  # preskoči ako već postoji

        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(local_path, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Downloaded {file_name}: {int(status.progress() * 100)}%")


# ---- MAIN LOOP ----
os.makedirs(LOCAL_DIR, exist_ok=True)
while True:
    download_files()
    time.sleep(POLL_INTERVAL)
