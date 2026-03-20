"""
🍇 Vinjak Festival App - Multi-Page

Stranice:
1. Home - Leaderboard za izbor Vinjaklije
2. Priče - Submission + Feed sa pričama
3. Sklekovi - Leaderboard za sklekove

Clean Code:
- Separacija concerns (config, data, UI)
- Type hints sveže
- Docstrings za sve funkcije
- DRY princip
- Error handling
"""

import os
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from dataclasses import dataclass

import streamlit as st
import pandas as pd
from google.oauth2 import service_account
import gspread

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIG
# ============================================================================


@dataclass
class GoogleSheetConfig:
    """Konfiguracija za Google Sheet pristup"""

    sheet_aktivnosti: Optional[str] = None
    sheet_price: Optional[str] = None
    sheet_sklekovi: Optional[str] = None
    sheet_igra: Optional[str] = None
    drive_slike_id: Optional[str] = None
    credentials: Optional[dict] = None

    def is_valid(self) -> bool:
        """Provera da li su kredencijali dostupni"""
        return self.credentials is not None


def load_configuration() -> GoogleSheetConfig:
    """
    Učitava konfiguraciju iz Streamlit Secrets ili os.env ili fajla

    Priority:
    1. Streamlit Secrets (st.secrets["google_credentials"])
    2. GOOGLE_CREDENTIALS_JSON env varijabla (kao string)
    3. Lokalni JSON fajl
    """
    logger.info("Učitavanje konfiguracije...")

    # Sheet ID-evi
    config = GoogleSheetConfig(
        sheet_aktivnosti=os.getenv("GOOGLE_SHEET_ID_AKTIVNOSTI")
        or st.secrets.get("google_sheet_id_aktivnosti"),
        sheet_price=os.getenv("GOOGLE_SHEET_ID_PRICE") or st.secrets.get("google_sheet_id_price"),
        sheet_sklekovi=os.getenv("GOOGLE_SHEET_ID_SKLEKOVI")
        or st.secrets.get("google_sheet_id_sklekovi"),
        sheet_igra=os.getenv("GOOGLE_SHEET_ID_VINJAK_IGRA")
        or st.secrets.get("google_sheet_id_vinjak_igra"),
        drive_slike_id=os.getenv("GOOGLE_DRIVE_ID_SLIKE")
        or st.secrets.get("google_drive_id_slike"),
    )

    # Kredencijali - Priority 1: Streamlit Secrets (TOML sekcija)
    if "google_credentials" in st.secrets:
        try:
            config.credentials = dict(st.secrets["google_credentials"])
            logger.info("✓ Kredencijali iz Streamlit Secrets")
        except Exception as e:
            logger.error(f"Greška pri čitanju Secrets: {e}")
    else:
        # Priority 2: environment varijabla kao JSON string
        creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if creds_json_str:
            try:
                config.credentials = json.loads(creds_json_str)
                logger.info("✓ Kredencijali iz environment varijable")
            except json.JSONDecodeError as e:
                logger.error(f"Greška pri parsiranju JSON-a: {e}")
        else:
            # Priority 3: lokalni fajl
            creds_file = Path("vinjak-fest-projekat-d1ab0846a2eb.json")
            if creds_file.exists():
                try:
                    with open(creds_file, "r", encoding="utf-8") as f:
                        config.credentials = json.load(f)
                    logger.info("✓ Kredencijali iz fajla")
                except Exception as e:
                    logger.error(f"Greška pri čitanju fajla: {e}")

    if not config.is_valid():
        logger.error("❌ Kredencijali nisu dostupni!")

    return config


# ============================================================================
# GOOGLE SHEETS OPERATIONS
# ============================================================================


@st.cache_resource
def get_cached_gsheet_connection(sheet_id: str, credentials: dict) -> Optional[gspread.Worksheet]:
    """Cache wrapper za Google Sheet konekciju"""
    if not sheet_id or not credentials:
        return None

    try:
        creds = service_account.Credentials.from_service_account_info(
            credentials,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc = gspread.authorize(creds)
        worksheet = gc.open_by_key(sheet_id).sheet1

        logger.info(f"✅ Konekcija na Sheet: {sheet_id[:20]}...")
        return worksheet

    except Exception as e:
        logger.error(f"❌ Greška pri konekciji: {e}")
        return None


class GoogleSheetManager:
    """Upravljač za Google Sheet operacije"""

    def __init__(self, config: GoogleSheetConfig):
        self.config = config

    def get_connection(self, sheet_id: str) -> Optional[gspread.Worksheet]:
        """Konekcija na Google Sheet"""
        if not self.config.is_valid():
            return None
        return get_cached_gsheet_connection(sheet_id, self.config.credentials)

    def load_data(self, sheet_id: str) -> pd.DataFrame:
        """Učitaj podatke iz Sheet-a"""
        if not sheet_id:
            logger.warning("Sheet ID nije unet")
            return pd.DataFrame()

        try:
            worksheet = self.get_connection(sheet_id)
            if not worksheet:
                return pd.DataFrame()

            data = worksheet.get_all_records()
            if not data:
                logger.warning("Sheet je prazan")
                return pd.DataFrame()

            df = pd.DataFrame(data)
            logger.info(f"✓ Učitano {len(df)} redaka")
            return df

        except Exception as e:
            logger.error(f"Greška pri učitavanju: {e}")
            st.error(f"❌ Greška pri učitavanju podataka: {e}")
            return pd.DataFrame()

    def append_row(self, sheet_id: str, row_data: list) -> bool:
        """Dodaj red u Google Sheet"""
        if not sheet_id:
            logger.error("Sheet ID nije unet")
            return False

        try:
            worksheet = self.get_connection(sheet_id)
            if not worksheet:
                return False

            # Koristi append_row sa user_entered_value za sigurnost
            worksheet.append_row(row_data, value_input_option="USER_ENTERED")
            logger.info(
                f"✓ Red dodan u Sheet (total redaka sada: {len(worksheet.get_all_records())})"
            )
            return True

        except Exception as e:
            logger.error(f"Greška pri dodavanju reda: {e}")
            import traceback

            traceback.print_exc()
            return False


# ============================================================================
# DATA PROCESSING
# ============================================================================


class DataProcessor:
    """Obrada i validacija podataka"""

    @staticmethod
    def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Očisti nazive kolona"""
        df.columns = df.columns.str.strip().str.lower()
        return df

    @staticmethod
    def find_column(df: pd.DataFrame, keywords: list, exclude: list = None) -> Optional[str]:
        """Pronađi kolonu po ključnim rečima"""
        exclude = exclude or []
        for col in df.columns:
            if any(kw in col for kw in keywords) and not any(ex in col for ex in exclude):
                return col
        return None

    @staticmethod
    def process_leaderboard_data(df: pd.DataFrame) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """Obrada podataka za leaderboard"""
        if df.empty:
            return None, "Nema podataka"

        try:
            df = DataProcessor.clean_columns(df)
            logger.info(f"Kolone: {list(df.columns)}")

            # Pronađi kolone
            ime_col = DataProcessor.find_column(
                df,
                keywords=["ime", "nadimak"],
                exclude=["timestamp", "prezime"],
            )
            prez_col = DataProcessor.find_column(df, keywords=["prezime"])
            poeni_col = DataProcessor.find_column(df, keywords=["poeni"])
            akt_col = DataProcessor.find_column(df, keywords=["aktivnost"])

            # Validacija
            if not all([ime_col, prez_col, poeni_col]):
                error_msg = f"Kolone nisu pronađene. Dostupne: {list(df.columns)}"
                logger.error(error_msg)
                return None, error_msg

            logger.info(
                f"Pronađene kolone: ime={ime_col}, prezime={prez_col}, "
                f"poeni={poeni_col}, aktivnost={akt_col}"
            )

            # Kreiraj puno ime
            df["ucesnik"] = (
                df[ime_col].astype(str).str.strip() + " " + df[prez_col].astype(str).str.strip()
            )

            # Konvertuj poene
            df["poeni_int"] = pd.to_numeric(df[poeni_col], errors="coerce").fillna(0).astype(int)

            df["_akt_col"] = akt_col

            logger.info(f"✅ Podaci obrađeni ({len(df)} redaka)")
            return df, None

        except Exception as e:
            error_msg = f"Greška pri obradi: {e}"
            logger.error(error_msg)
            return None, error_msg

    @staticmethod
    def create_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
        """Kreiraj ranglistu iz podataka"""
        leaderboard = df.groupby("ucesnik")["poeni_int"].sum().reset_index()
        leaderboard.columns = ["Učesnik", "Poeni"]
        leaderboard = leaderboard.sort_values("Poeni", ascending=False).reset_index(drop=True)
        leaderboard["Rang"] = range(1, len(leaderboard) + 1)
        return leaderboard


# ============================================================================
# UI SETUP
# ============================================================================


def setup_page_config() -> None:
    """Inicijalizuj Streamlit konfiguraciju"""
    st.set_page_config(
        page_title="🍇 Vinjak Festival",
        page_icon="🍇",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def setup_custom_css() -> None:
    """Postavi custom CSS"""
    st.markdown(
        """
        <style>
        .main {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .stMetric {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #ffd700;
        }
        h1 {
            text-align: center;
            color: #ffd700;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }
        h2 {
            color: #ffd700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# UI PAGES
# ============================================================================


def page_home(manager: GoogleSheetManager) -> None:
    """Leaderboard stranica"""
    st.title("IZBOR ZA VINJAKLIJU")
    st.markdown("#### Live ranglist - Realtime ažuriranje")

    # Refresh dugme
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Osvežite", width="stretch"):
            st.cache_resource.clear()
            st.rerun()

    # Učitaj podatke
    raw_df = manager.load_data(manager.config.sheet_aktivnosti)
    if raw_df.empty:
        st.warning("⚠️ Nema podataka")
        return

    # Obrada
    df, error = DataProcessor.process_leaderboard_data(raw_df)
    if error:
        st.error(f"❌ {error}")
        return

    # Kreiraj ranglistu
    leaderboard = DataProcessor.create_leaderboard(df)

    # TOP 3
    st.markdown("---")
    st.subheader("🏆 TOP 3 VINJAČKA UŽIVAOCA")

    top3 = leaderboard.head(3).copy()
    cols = st.columns(3)
    medals = ["🥇 VINJAKLIJA", "🥈 DRUGOVINJAK", "🥉 TROVINJAK"]

    for col, medal in zip(cols, medals):
        with col:
            if len(top3) > 0:
                row = top3.iloc[0]
                st.metric(medal, row["Učesnik"], f"{int(row['Poeni'])} poena")
                top3 = top3.iloc[1:]
            else:
                st.metric(medal, "---", "")

    # Kompletna ranglista
    st.markdown("---")
    st.subheader("📊 KOMPLETNA RANGLISTA")
    display_df = leaderboard[["Rang", "Učesnik", "Poeni"]].copy()
    st.dataframe(display_df, width="stretch", hide_index=True, height=400)


def page_price(manager: GoogleSheetManager) -> None:
    """Priče stranica sa submission formom i feed-om"""
    st.title("VINJAK ISPOVEDAONICA")
    st.markdown(
        "Vreme je da tvoje Vinjačke dogodovštine napokon dobiju platformu! "
        "Napiši svoju priču i deli sa drugima!"
    )

    # SUBMISSION FORMA
    st.subheader("✍️ Podeli svoju priču!")

    with st.form("story_form", clear_on_submit=True):
        name = st.text_input("Tvoje ime / Nadimak", max_chars=100)
        story = st.text_area("Tvoja dogodovština ili ispovest", height=150, max_chars=1000)
        submitted = st.form_submit_button("📝 Pošalji priču", use_container_width=True)

        if submitted:
            if not name or not story:
                st.error("❌ Popuni sva polja!")
            else:
                timestamp = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                row = [timestamp, name, story]

                logger.info(f"Slanje reda: {row}")
                st.info(f"Debug: Dodavam red: {row}")

                if manager.append_row(manager.config.sheet_price, row):
                    st.success("✅ Priča poslata!")
                    time.sleep(1)
                    st.cache_resource.clear()
                    st.rerun()
                else:
                    st.error("❌ Greška pri slanju priče")

    # FEED
    st.markdown("---")
    st.subheader("📰 FEED PRIČA")

    df = manager.load_data(manager.config.sheet_price)
    if df.empty:
        st.info("📝 Nema priča - budi prvi!")
        return

    df = DataProcessor.clean_columns(df)

    timestamp_col = DataProcessor.find_column(df, keywords=["timestamp"])
    name_col = DataProcessor.find_column(df, keywords=["ime", "nadimak"], exclude=["timestamp"])
    story_col = DataProcessor.find_column(df, keywords=["ispovest", "priča", "dogodovština"])

    if not all([timestamp_col, name_col, story_col]):
        st.error("❌ Kolone nisu pronađene")
        return

    # Prikaži priče (novije prvo)
    for idx, row in df.iloc[::-1].iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{row[name_col]}**")
                st.write(row[story_col])
            with col2:
                st.caption(f"⏰ {row[timestamp_col]}")


def page_sklekovi(manager: GoogleSheetManager) -> None:
    """Sklekovi leaderboard stranica"""
    st.title("VINJAK SKLEKOVI")
    st.markdown("#### Tabela najsklekača")

    if not manager.config.sheet_sklekovi:
        st.error("❌ Sklekovi leaderboard nije konfiguriran")
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Osvežite", width="stretch"):
            st.cache_resource.clear()
            st.rerun()

    df = manager.load_data(manager.config.sheet_sklekovi)
    if df.empty:
        st.warning("⚠️ Nema podataka")
        return

    try:
        df = DataProcessor.clean_columns(df)

        ime_col = DataProcessor.find_column(df, keywords=["ime", "nadimak"], exclude=["timestamp"])
        sklekovi_col = DataProcessor.find_column(df, keywords=["sklekovi", "broj", "odradjenih"])

        if not all([ime_col, sklekovi_col]):
            st.error("❌ Kolone nisu pronađene!")
            st.info(f"Dostupne kolone: {list(df.columns)}")
            return

        df["broj_sklekova"] = (
            pd.to_numeric(df[sklekovi_col], errors="coerce").fillna(0).astype(int)
        )

        leaderboard = df[[ime_col, "broj_sklekova"]].copy()
        leaderboard.columns = ["Učesnik", "Sklekovi"]
        leaderboard = leaderboard.sort_values("Sklekovi", ascending=False).reset_index(drop=True)
        leaderboard["Rang"] = range(1, len(leaderboard) + 1)

        # TOP 3
        st.markdown("---")
        st.subheader("🏆 TOP 3 SKLEKAČA")

        top3 = leaderboard.head(3).copy()
        cols = st.columns(3)
        medals = ["🥇 SKLEK BOSS", "🥈 SKLEK MASTER", "🥉 SKLEK PRO"]

        for col, medal in zip(cols, medals):
            with col:
                if len(top3) > 0:
                    row = top3.iloc[0]
                    st.metric(medal, row["Učesnik"], f"{int(row['Sklekovi'])} sklekova")
                    top3 = top3.iloc[1:]
                else:
                    st.metric(medal, "---", "")

        # Kompletna ranglista
        st.markdown("---")
        st.subheader("📊 KOMPLETNA RANGLISTA")
        display_df = leaderboard[["Rang", "Učesnik", "Sklekovi"]].copy()
        st.dataframe(display_df, width="stretch", hide_index=True, height=400)

    except Exception as e:
        st.error(f"❌ Greška pri obradi: {e}")


def page_igra(manager: GoogleSheetManager) -> None:
    """Leaderboard za Vinjak igricu"""
    st.title("🎮 VINJAK IGRICA 🎮")
    st.markdown("#### Leaderboard igrača")

    if not manager.config.sheet_igra:
        st.error("❌ Igrica leaderboard nije konfiguriran")
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Osvežite", width="stretch"):
            st.cache_resource.clear()
            st.rerun()

    df = manager.load_data(manager.config.sheet_igra)
    if df.empty:
        st.warning("⚠️ Nema podataka")
        return

    try:
        df = DataProcessor.clean_columns(df)
        logger.info(f"Kolone iz igrice: {list(df.columns)}")

        # Pronađi kolone - fleksibilna pretraga
        ime_col = DataProcessor.find_column(df, keywords=["name"], exclude=["timestamp"])
        poeni_col = DataProcessor.find_column(df, keywords=["poeni", "score", "rezultat"])

        if not all([ime_col, poeni_col]):
            st.error("❌ Kolone nisu pronađene!")
            st.info(f"Dostupne kolone: {list(df.columns)}")
            return

        # Konvertuj poene
        df["poeni_int"] = pd.to_numeric(df[poeni_col], errors="coerce").fillna(0).astype(int)

        # Sortiraj po poeni (bez groupby - svakog igrača samo jednom)
        leaderboard = df[[ime_col, "poeni_int"]].copy()
        leaderboard.columns = ["Igrač", "Poeni"]
        leaderboard = leaderboard.sort_values("Poeni", ascending=False).reset_index(drop=True)
        leaderboard["Rang"] = range(1, len(leaderboard) + 1)

        # TOP 3
        st.markdown("---")
        st.subheader("🏆 TOP 3 IGRAČA")

        top3 = leaderboard.head(3).copy()
        cols = st.columns(3)
        medals = ["🥇 BROJ 1", "🥈 BROJ 2", "🥉 BROJ 3"]

        for col, medal in zip(cols, medals):
            with col:
                if len(top3) > 0:
                    row = top3.iloc[0]
                    st.metric(medal, row["Igrač"], f"{int(row['Poeni'])} poena")
                    top3 = top3.iloc[1:]
                else:
                    st.metric(medal, "---", "")

        # Kompletna ranglista
        st.markdown("---")
        st.subheader("📊 KOMPLETNA RANGLISTA")
        display_df = leaderboard[["Rang", "Igrač", "Poeni"]].copy()
        st.dataframe(display_df, width="stretch", hide_index=True, height=400)

    except Exception as e:
        logger.error(f"Greška pri obradi igrice: {e}")
        st.error(f"❌ Greška pri obradi: {e}")


def page_galery(manager: GoogleSheetManager) -> None:
    """Galerija oslikanih flase - direktno sa Google Drive-a"""
    st.title("GALERIJA OSLIKANIH FLAŠA VINJAKA")
    st.markdown("#### Sve oslikane flaše sa festivala, a i malo pre...")

    if not manager.config.drive_slike_id:
        st.error("❌ Google Drive folder nije konfiguriran")
        return

    try:
        # Konekcija na Google Drive
        creds = service_account.Credentials.from_service_account_info(
            manager.config.credentials,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
        import io

        service = build("drive", "v3", credentials=creds)

        # Preuzmi listu fajlova iz foldera
        results = (
            service.files()
            .list(
                q=f"'{manager.config.drive_slike_id}' in parents and trashed=false and mimeType contains 'image/'",
                fields="files(id, name, mimeType)",
                pageSize=100,
            )
            .execute()
        )
        files = results.get("files", [])

        if not files:
            st.info("📝 Nema slika u Google Drive folderu")
            return

        # Sortiraj po imenu
        files = sorted(files, key=lambda x: x["name"])

        st.subheader(f"📸 {len(files)} Oslikanih Flaša Vinjaka")

        # Prikazi u grid-u (3 kolone)
        cols = st.columns(3)
        for idx, file in enumerate(files):
            col = cols[idx % 3]
            with col:
                try:
                    # Preuzmi sliku kao binary
                    request = service.files().get_media(fileId=file["id"])
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False

                    while not done:
                        status, done = downloader.next_chunk()

                    fh.seek(0)

                    # Prikaži sliku
                    st.image(fh, width="stretch")

                except Exception as e:
                    st.error(f"Greška pri učitavanju: {file['name']}")
                    logger.error(f"Greška pri učitavanju slike {file['name']}: {e}")

    except Exception as e:
        logger.error(f"Greška pri učitavanju galerije: {e}")
        st.error(f"❌ Greška pri učitavanju galerije: {e}")


# ============================================================================
# MAIN
# ============================================================================


def main() -> None:
    """Main entry point"""
    # Setup
    setup_page_config()
    setup_custom_css()

    # Konfiguracija
    config = load_configuration()
    if not config.is_valid():
        st.error("❌ GoogleCredentialsnisu dostupni!")
        st.info("Postavite GOOGLE_CREDENTIALS_JSON environment varijablu")
        st.stop()

    manager = GoogleSheetManager(config)

    # Sidebar navigacija
    st.sidebar.title("🍇 VINJAK FESTIVAL")
    page = st.sidebar.radio(
        "Odaberi stranicu:",
        ["🏆 Vinjaklija", "📖 Ispovedaonica", "💪 Sklekovi", "🎮 Igrica", "🍇 Galerija"],
    )

    # Render stranica
    if page == "🏆 Vinjaklija":
        page_home(manager)
    elif page == "📖 Ispovedaonica":
        page_price(manager)
    elif page == "💪 Sklekovi":
        page_sklekovi(manager)
    elif page == "🎮 Igrica":
        page_igra(manager)
    elif page == "🍇 Galerija":
        page_galery(manager)

    # Auto refresh
    st.markdown("---")
    st.sidebar.markdown("---")

    refresh_interval = st.sidebar.slider(
        "Osvežavanje (sekundi)", min_value=5, max_value=120, value=30, step=5
    )

    now = datetime.now().strftime("%H:%M:%S")
    st.sidebar.caption(f"⏰ {now} | Sledeće: ~{refresh_interval}s")

    time.sleep(refresh_interval)
    st.rerun()


if __name__ == "__main__":
    main()
