"""
🍇 VINJAK FESTIVAL MASTER SYNCER

Unified script koji upravlja svim sync operacijama:
1. Google Drive Image Downloader - skida slike sa Drive-a
2. Image Pixelizer - pikselizira i obradi slike
3. Ispovedaonica Syncer - sinhronizuje priče
4. Leaderboard Syncer - sinhronizuje leaderboard sa Sheet-om

Config iz .env:
- GOOGLE_DRIVE_ID_SLIKE
- GOOGLE_SHEET_ID_PRICE (ispovedaonica)
- GOOGLE_SHEET_ID_VINJAK_IGRA (leaderboard)
- GOOGLE_CREDENTIALS_JSON
"""

import os
import json
import io
import time
import logging
import sys
from typing import Optional, Dict, List
from threading import Thread

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
import gspread
from rembg import remove
from PIL import Image, ImageEnhance
from dotenv import load_dotenv

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(threadName)s] - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("vinjak_festival_master.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIG
# ============================================================================

load_dotenv()

# Google Drive
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_ID_SLIKE")
CREDS_JSON_STR = os.getenv("GOOGLE_CREDENTIALS_JSON")

# Google Sheets
SHEET_ID_PRICE = os.getenv("GOOGLE_SHEET_ID_ISPOVEDAONICA")
SHEET_ID_LEADERBOARD = os.getenv("GOOGLE_SHEET_ID_VINJAK_IGRA")

# Directories
INPUT_DIR = "slike/unedited"
OUTPUT_DIR = "slike/flase"
LEADERBOARD_FILE = "leaderboard.xlsx"
BACKUP_DIR = "leaderboard_backups"

# Intervals
DRIVE_POLL_INTERVAL = 120
IMAGE_CHECK_INTERVAL = 360
PRICE_SYNC_INTERVAL = 120
LEADERBOARD_POLL_INTERVAL = 120

# Image processing
PIXEL_SIZE = 24
NUM_COLORS = 256
CONTRAST_FACTOR = 1.2
COLOR_FACTOR = 1.2

# ============================================================================
# CREDENTIALS
# ============================================================================


def load_credentials() -> Optional[dict]:
    """Učitaj Google credentials"""
    if not CREDS_JSON_STR:
        logger.error("❌ GOOGLE_CREDENTIALS_JSON nije unet!")
        return None

    try:
        creds = json.loads(CREDS_JSON_STR)
        logger.info("✓ Kredencijali učitani")
        return creds
    except json.JSONDecodeError as e:
        logger.error(f"❌ Greška pri parsiranju JSON-a: {e}")
        return None


# ============================================================================
# DRIVE OPERATIONS
# ============================================================================


def get_drive_service():
    """Konekcija na Google Drive API"""
    creds = load_credentials()
    if not creds or not DRIVE_FOLDER_ID:
        logger.error("❌ Nema kredencijala ili GOOGLE_DRIVE_ID_SLIKE!")
        return None

    try:
        creds_obj = service_account.Credentials.from_service_account_info(
            creds,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        service = build("drive", "v3", credentials=creds_obj)
        logger.info("✅ Konekcija na Drive API")
        return service
    except Exception as e:
        logger.error(f"❌ Drive API greška: {e}")
        return None


def download_files(service):
    """Skini nove slike sa Google Drive-a"""
    if not service:
        return

    try:
        results = (
            service.files()
            .list(
                q=f"'{DRIVE_FOLDER_ID}' in parents and trashed=false",
                fields="files(id, name, mimeType)",
            )
            .execute()
        )
        drive_files = results.get("files", [])

        if not drive_files:
            logger.debug("📁 Nema fajlova na Drive-u")
            return

        logger.info(f"📥 Pronađeno {len(drive_files)} fajlova na Drive-u")

        local_files = [
            f for f in os.listdir(INPUT_DIR) if os.path.isfile(os.path.join(INPUT_DIR, f))
        ]

        if len(drive_files) == len(local_files):
            logger.debug("✅ Svi fajlovi već preuzeti")
            return

        for file in drive_files:
            file_id = file["id"]
            file_name = file["name"]
            local_path = os.path.join(INPUT_DIR, file_name)

            if os.path.exists(local_path):
                continue

            try:
                request = service.files().get_media(fileId=file_id)
                fh = io.FileIO(local_path, "wb")
                downloader = MediaIoBaseDownload(fh, request)
                done = False

                while not done:
                    status, done = downloader.next_chunk()
                    progress = int(status.progress() * 100) if status else 0
                    if progress % 25 == 0:
                        logger.info(f"📥 {file_name}: {progress}%")

                logger.info(f"✅ Preuzeto: {file_name}")
            except Exception as e:
                logger.error(f"❌ Greška pri preuzimanju {file_name}: {e}")

    except Exception as e:
        logger.error(f"❌ Greška pri čitanju Drive foldera: {e}")


# ============================================================================
# IMAGE PROCESSING
# ============================================================================


def process_image(file_path: str, output_dir: str) -> bool:
    """Obradi sliku"""
    try:
        file_name = os.path.basename(file_path)
        output_path = os.path.join(output_dir, os.path.splitext(file_name)[0] + "_pixel.png")

        logger.info(f"⚙️  Obrada {file_name}...")

        with open(file_path, "rb") as f:
            input_data = f.read()

        output_data = remove(input_data)
        img = Image.open(io.BytesIO(output_data)).convert("RGBA")

        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)

        small = img.resize(
            (max(1, img.width // PIXEL_SIZE), max(1, img.height // PIXEL_SIZE)),
            resample=Image.NEAREST,
        )
        pixelized = small.resize(img.size, Image.NEAREST)

        pixelized = ImageEnhance.Contrast(pixelized).enhance(CONTRAST_FACTOR)
        pixelized = ImageEnhance.Color(pixelized).enhance(COLOR_FACTOR)

        pixelized = pixelized.convert("P", palette=Image.ADAPTIVE, colors=NUM_COLORS)
        pixelized.save(output_path)

        logger.info(f"✅ {file_name} → {output_path}")
        return True

    except Exception as e:
        logger.error(f"❌ Greška pri obradi {file_path}: {e}")
        return False


def get_files_with_mtime(folder: str) -> Dict[str, float]:
    """Vrati dict {file_path: mtime}"""
    supported_ext = [".png", ".jpg", ".jpeg"]
    files = {}

    if not os.path.exists(folder):
        return files

    for f in os.listdir(folder):
        if os.path.splitext(f)[1].lower() in supported_ext:
            path = os.path.join(folder, f)
            files[path] = os.path.getmtime(path)

    return files


# ============================================================================
# SHEET OPERATIONS
# ============================================================================


def get_gsheet_connection(sheet_id: str) -> Optional[gspread.Worksheet]:
    """Konekcija na Google Sheet"""
    if not sheet_id:
        return None

    creds = load_credentials()
    if not creds:
        return None

    try:
        creds_obj = service_account.Credentials.from_service_account_info(
            creds,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc = gspread.authorize(creds_obj)
        worksheet = gc.open_by_key(sheet_id).sheet1
        return worksheet

    except Exception as e:
        logger.error(f"❌ Greška pri konekciji na Sheet {sheet_id[:20]}...: {e}")
        return None


# ============================================================================
# ISPOVEDAONICA SYNCER
# ============================================================================


def find_columns(df: pd.DataFrame) -> tuple:
    """Pronađi ime i priču kolone"""
    df.columns = df.columns.str.strip().str.lower()
    cols = list(df.columns)

    name_col = None
    for col in cols:
        if col in ["tvoje ime / nadimak", "ime", "nadimak"]:
            name_col = col
            break
        if "ime" in col and "timestamp" not in col:
            name_col = col
            break

    story_col = None
    for col in cols:
        if "događovština" in col or "ispovest" in col or "priča" in col:
            if "timestamp" not in col and "ime" not in col:
                story_col = col
                break

    return name_col, story_col


def process_stories(df: pd.DataFrame) -> List[Dict[str, str]]:
    """Konvertuj DataFrame u listu priča"""
    try:
        name_col, story_col = find_columns(df)

        stories = []
        for idx, row in df.iterrows():
            name = str(row[name_col]).strip()
            story = str(row[story_col]).strip()

            if not name or not story or name.lower() == "nan" or story.lower() == "nan":
                continue

            if len(name) < 2 or len(story) < 5:
                continue

            stories.append({"name": name, "story": story})

        logger.info(f"✓ Procesuirano {len(stories)} priča")
        return stories

    except Exception as e:
        logger.error(f"❌ Greška pri obradi priča: {e}")
        return []


def sync_stories(worksheet: gspread.Worksheet) -> None:
    """Sinhronizuj priče"""
    try:
        data = worksheet.get_all_records()
        if not data:
            logger.debug("📝 Nema priča na Sheet-u")
            return

        df = pd.DataFrame(data)
        stories = process_stories(df)

        if stories:
            with open("price.json", "w", encoding="utf-8") as f:
                json.dump(stories, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Priče sačuvane: {len(stories)} redaka")

    except Exception as e:
        logger.error(f"❌ Greška pri sync-u priča: {e}")


# ============================================================================
# LEADERBOARD SYNCER
# ============================================================================


# ============================================================================
# SYNCER THREADS
# ============================================================================


def thread_drive_downloader():
    """Thread za preuzimanje slike sa Drive-a"""
    logger.info("[THREAD] Drive downloader pokrenut")
    os.makedirs(INPUT_DIR, exist_ok=True)

    service = get_drive_service()
    if not service:
        logger.error("[THREAD] ❌ Drive downloader ne može da se konektuje")
        return

    counter = 0
    try:
        while True:
            counter += 1
            logger.info(f"[DRIVE] Skeniranje #{counter}")
            download_files(service)
            time.sleep(DRIVE_POLL_INTERVAL)
    except Exception as e:
        logger.error(f"[THREAD] ❌ Drive downloader kritična greška: {e}")


def thread_image_processor():
    """Thread za obradu slike"""
    logger.info("[THREAD] Image processor pokrenut")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    processed_files = {}
    counter = 0

    try:
        while True:
            counter += 1
            logger.info(f"[IMAGE] Skeniranje #{counter}")
            files = get_files_with_mtime(INPUT_DIR)

            if files:
                for path, mtime in files.items():
                    if path not in processed_files or processed_files[path] < mtime:
                        process_image(path, OUTPUT_DIR)
                        processed_files[path] = mtime
            else:
                logger.debug("[IMAGE] Nema slike za obradu")

            time.sleep(IMAGE_CHECK_INTERVAL)
    except Exception as e:
        logger.error(f"[THREAD] ❌ Image processor kritična greška: {e}")


def thread_ispovedaonica_syncer():
    """Thread za sync priča"""
    logger.info("[THREAD] Ispovedaonica syncer pokrenut")

    worksheet = get_gsheet_connection(SHEET_ID_PRICE)
    if not worksheet:
        logger.error("[THREAD] ❌ Ispovedaonica syncer ne može da se konektuje")
        return

    counter = 0
    try:
        while True:
            counter += 1
            logger.info(f"[PRIČE] Sinhronizacija #{counter}")
            sync_stories(worksheet)
            time.sleep(PRICE_SYNC_INTERVAL)
    except Exception as e:
        logger.error(f"[THREAD] ❌ Ispovedaonica syncer kritična greška: {e}")


def thread_leaderboard_syncer():
    """Thread za sync leaderboard-a - upload lokalnog fajla na Google Sheet"""
    logger.info("[THREAD] Leaderboard syncer pokrenut")

    worksheet = get_gsheet_connection(SHEET_ID_LEADERBOARD)
    if not worksheet:
        logger.error("[THREAD] ❌ Leaderboard syncer ne može da se konektuje")
        return

    last_modified = None
    counter = 0

    try:
        while True:
            counter += 1
            try:
                # Proveri da li fajl uopšte postoji
                if not os.path.exists(LEADERBOARD_FILE):
                    logger.debug("[LEADERBOARD] Fajl ne postoji još uvek")
                    time.sleep(LEADERBOARD_POLL_INTERVAL)
                    continue

                # Proveri da li je fajl izmenjen od poslednjeg sync-a
                current_modified = os.path.getmtime(LEADERBOARD_FILE)
                if last_modified is not None and current_modified == last_modified:
                    logger.debug(f"[LEADERBOARD] Sinhronizacija #{counter} - ✓ Nema promena")
                    time.sleep(LEADERBOARD_POLL_INTERVAL)
                    continue

                # Učitaj lokalni fajl i upload-uj na Sheet
                df = pd.read_excel(LEADERBOARD_FILE)
                df.sort_values("Score", ascending=False, inplace=True)

                # Očisti sheet i upiši sve iznova
                worksheet.clear()
                worksheet.update([df.columns.tolist()] + df.values.tolist())

                last_modified = current_modified
                logger.info(
                    f"✅ [LEADERBOARD] Sinhronizacija #{counter} - upload {len(df)} redaka"
                )

            except Exception as e:
                logger.error(f"[LEADERBOARD] Greška pri sync-u: {e}")

            time.sleep(LEADERBOARD_POLL_INTERVAL)

    except KeyboardInterrupt:
        logger.info("[LEADERBOARD] Zaustavljen")
    except Exception as e:
        logger.error(f"[THREAD] ❌ Leaderboard syncer kritična greška: {e}")


# ============================================================================
# MAIN
# ============================================================================


def main():
    """Main entry point - pokreni sve threadove"""
    logger.info("=" * 80)
    logger.info("🍇 VINJAK FESTIVAL MASTER SYNCER - STARTOVANJE")
    logger.info("=" * 80)

    # Validacija config-a
    if not CREDS_JSON_STR:
        logger.error("❌ GOOGLE_CREDENTIALS_JSON nije unet u .env!")
        sys.exit(1)

    if not all([DRIVE_FOLDER_ID, SHEET_ID_PRICE, SHEET_ID_LEADERBOARD]):
        logger.error("❌ Nedostaju Sheet ID-evi u .env!")
        sys.exit(1)

    logger.info("✅ Konfiguracija validna")
    logger.info(f"  Drive Folder: {DRIVE_FOLDER_ID[:20]}...")
    logger.info(f"  Price Sheet: {SHEET_ID_PRICE[:20]}...")
    logger.info(f"  Leaderboard Sheet: {SHEET_ID_LEADERBOARD[:20]}...")

    # Kreiraj direktorijume
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Kreiraj i pokreni threadove
    threads = [
        Thread(target=thread_drive_downloader, daemon=True, name="DriveDownloader"),
        Thread(target=thread_image_processor, daemon=True, name="ImageProcessor"),
        Thread(target=thread_ispovedaonica_syncer, daemon=True, name="IspovedaonnicaSyncer"),
        Thread(target=thread_leaderboard_syncer, daemon=True, name="LeaderboardSyncer"),
    ]

    for thread in threads:
        thread.start()
        logger.info(f"✅ {thread.name} thread pokrenut")

    logger.info("=" * 80)
    logger.info("🍇 SVI SYNCER-I SU AKTIVNI")
    logger.info("=" * 80)

    try:
        # Čekaj na threadove (daemon threads će se okinuti sa main-om)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n⏹️  Master syncer zaustavljen od strane korisnika")
        sys.exit(0)


if __name__ == "__main__":
    main()
