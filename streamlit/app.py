"""
🍇 Vinjak Festival App - Multi-Page sa Navbar-om

Stranice:
1. Vinjaklija - Leaderboard za izbor Vinjaklije
2. Ispovedaonica - Submission + Feed sa pričama
3. Sklekovi - Leaderboard za sklekove
4. Igrica - Leaderboard za Vinjak igricu
5. Galerija - Oslikane flaše sa Drive-a

Clean Code:
- Separacija concerns (config, data, UI)
- Type hints sveže
- Docstrings za sve funkcije
- DRY princip
- Error handling
- Navbar na vrhu umesto sidebar-a
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

            ime_col = DataProcessor.find_column(
                df,
                keywords=["ime", "nadimak"],
                exclude=["timestamp", "prezime"],
            )
            prez_col = DataProcessor.find_column(df, keywords=["prezime"])
            poeni_col = DataProcessor.find_column(df, keywords=["poeni"])
            akt_col = DataProcessor.find_column(df, keywords=["aktivnost"])

            if not all([ime_col, prez_col, poeni_col]):
                error_msg = f"Kolone nisu pronađene. Dostupne: {list(df.columns)}"
                logger.error(error_msg)
                return None, error_msg

            logger.info(
                f"Pronađene kolone: ime={ime_col}, prezime={prez_col}, "
                f"poeni={poeni_col}, aktivnost={akt_col}"
            )

            df["ucesnik"] = (
                df[ime_col].astype(str).str.strip() + " " + df[prez_col].astype(str).str.strip()
            )

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
        page_title="Vinjak Festival",
        page_icon="🍇",
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def setup_custom_css() -> None:
    """Postavi custom CSS - navbar na vrhu sa toplom braon/žutom/ljubičastom paletom"""
    st.markdown(
        """
        <style>
        /* Hide sidebar */
        [data-testid="stSidebar"] { display: none; }
        
        /* Main */
        .main {
            background: linear-gradient(135deg, #5a3f4b 0%, #8b6f7f 100%);
            color: white;
            padding: 0 !important;
        }
        [data-testid="stAppViewContainer"] { padding: 0 !important; }
        
        /* ===== NAVBAR ===== */
        .navbar {
            background: linear-gradient(90deg, #6b4423 0%, #8b5a3c 30%, #7d5a57 70%, #6b4a63 100%);
            padding: 1.2rem 2rem;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
            margin-bottom: 2rem;
            border-bottom: 3px solid #d4a574;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-radius: 0 0 15px 15px;
        }
        
        .navbar-title {
            font-size: 1.8rem;
            font-weight: 900;
            color: #ffd699;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.4);
            letter-spacing: 1px;
        }
        
        /* Navbar buttons - styling */
        .nav-button {
            background: linear-gradient(135deg, #d4a574 0%, #e8c4a0 100%) !important;
            color: #6b4423 !important;
            font-weight: 700 !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 8px 16px !important;
            transition: all 0.3s ease !important;
        }
        
        .nav-button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 12px rgba(212, 165, 116, 0.4) !important;
        }
        
        /* Content wrapper */
        .content-wrapper {
            padding: 0 3rem;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        /* Components */
        .stMetric {
            background: linear-gradient(135deg, rgba(212, 165, 116, 0.15) 0%, rgba(212, 165, 116, 0.05) 100%);
            padding: 20px;
            border-radius: 12px;
            border-left: 5px solid #d4a574;
            border-top: 1px solid rgba(212, 165, 116, 0.3);
            backdrop-filter: blur(10px);
        }
        
        h1 {
            text-align: center;
            color: #ffd699;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
            margin-top: 2rem;
            font-size: 2.5rem;
            letter-spacing: 0.5px;
        }
        
        h2 { 
            color: #d4a574;
            font-weight: 700;
        }
        
        .stForm {
            background: linear-gradient(135deg, rgba(212, 165, 116, 0.1) 0%, rgba(212, 165, 116, 0.05) 100%);
            padding: 1.5rem;
            border-radius: 12px;
            border: 2px solid rgba(212, 165, 116, 0.3);
        }
        
        .stButton > button {
            background: linear-gradient(135deg, #d4a574 0%, #e8c4a0 100%) !important;
            color: #6b4423 !important;
            font-weight: bold !important;
            border: none !important;
            border-radius: 8px !important;
            transition: all 0.3s ease !important;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 12px rgba(212, 165, 116, 0.4) !important;
        }
        
        /* Dataframe styling */
        [data-testid="stDataFrame"] {
            background: rgba(212, 165, 116, 0.08) !important;
            border-radius: 10px !important;
            border: 1px solid rgba(212, 165, 116, 0.2) !important;
        }
        
        /* Text input */
        .stTextInput, .stTextArea {
            color: white !important;
        }
        
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            background-color: rgba(107, 68, 35, 0.6) !important;
            color: white !important;
            border: 1px solid rgba(212, 165, 116, 0.3) !important;
        }
        
        /* Info/Warning boxes */
        [data-testid="stInfo"] {
            background-color: rgba(212, 165, 116, 0.15) !important;
            border-left: 4px solid #d4a574 !important;
        }
        
        [data-testid="stWarning"] {
            background-color: rgba(180, 120, 70, 0.2) !important;
            border-left: 4px solid #d4a574 !important;
        }
        
        [data-testid="stSuccess"] {
            background-color: rgba(150, 180, 80, 0.2) !important;
            border-left: 4px solid #96b450 !important;
        }
        
        [data-testid="stError"] {
            background-color: rgba(220, 100, 100, 0.2) !important;
            border-left: 4px solid #dc6464 !important;
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

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Osvežite", width="stretch"):
            st.cache_resource.clear()
            st.rerun()

    raw_df = manager.load_data(manager.config.sheet_aktivnosti)
    if raw_df.empty:
        st.warning("⚠️ Nema podataka")
        return

    df, error = DataProcessor.process_leaderboard_data(raw_df)
    if error:
        st.error(f"❌ {error}")
        return

    leaderboard = DataProcessor.create_leaderboard(df)

    st.markdown("---")
    st.subheader("TOP 3 VINJAČKA UŽIVAOCA")

    top3 = leaderboard.head(3).copy()
    cols = st.columns(3)
    medals = ["VINJAKLIJA", "DRUGOVINJAK", "TROVINJAK"]

    for col, medal in zip(cols, medals):
        with col:
            if len(top3) > 0:
                row = top3.iloc[0]
                st.metric(medal, row["Učesnik"], f"{int(row['Poeni'])} poena")
                top3 = top3.iloc[1:]
            else:
                st.metric(medal, "---", "")

    st.markdown("---")
    st.subheader("KOMPLETNA RANGLISTA")
    display_df = leaderboard[["Rang", "Učesnik", "Poeni"]].copy()
    st.dataframe(display_df, width="stretch", hide_index=True, height=400)


def page_price(manager: GoogleSheetManager) -> None:
    """Priče stranica sa submission formom i feed-om"""
    st.title("VINJAK ISPOVEDAONICA")
    st.markdown("Vreme je da tvoje Vinjačke dogodovštine napokon dobiju platformu!")

    st.subheader("Podeli svoju priču!")

    with st.form("story_form", clear_on_submit=True):
        name = st.text_input("Tvoje ime / Nadimak", max_chars=100)
        story = st.text_area("Tvoja događovština ili ispovest", height=150, max_chars=1000)
        submitted = st.form_submit_button("Pošalji priču", use_container_width=True)

        if submitted:
            if not name or not story:
                st.error("❌ Popuni sva polja!")
            else:
                timestamp = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                row = [timestamp, name, story]

                logger.info(f"Slanje reda: {row}")

                if manager.append_row(manager.config.sheet_price, row):
                    st.success("✅ Priča poslata!")
                    time.sleep(1)
                    st.cache_resource.clear()
                    st.rerun()
                else:
                    st.error("❌ Greška pri slanju priče")

    st.markdown("---")
    st.subheader("FEED PRIČA")

    df = manager.load_data(manager.config.sheet_price)
    if df.empty:
        st.info("Nema priča - budi prvi!")
        return

    df = DataProcessor.clean_columns(df)

    timestamp_col = DataProcessor.find_column(df, keywords=["timestamp"])
    name_col = DataProcessor.find_column(df, keywords=["ime", "nadimak"], exclude=["timestamp"])
    story_col = DataProcessor.find_column(df, keywords=["ispovest", "priča", "dogodovština"])

    if not all([timestamp_col, name_col, story_col]):
        st.error("❌ Kolone nisu pronađene")
        return

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
        if st.button("Osvežite", width="stretch", key="sklekovi_refresh"):
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

        st.markdown("---")
        st.subheader("TOP 3 SKLEKAČA")

        top3 = leaderboard.head(3).copy()
        cols = st.columns(3)
        medals = ["SKLEK BOSS", "SKLEK MASTER", "SKLEK PRO"]

        for col, medal in zip(cols, medals):
            with col:
                if len(top3) > 0:
                    row = top3.iloc[0]
                    st.metric(medal, row["Učesnik"], f"{int(row['Sklekovi'])} sklekova")
                    top3 = top3.iloc[1:]
                else:
                    st.metric(medal, "---", "")

        st.markdown("---")
        st.subheader("KOMPLETNA RANGLISTA")
        display_df = leaderboard[["Rang", "Učesnik", "Sklekovi"]].copy()
        st.dataframe(display_df, width="stretch", hide_index=True, height=400)

    except Exception as e:
        st.error(f"❌ Greška pri obradi: {e}")


def page_igra(manager: GoogleSheetManager) -> None:
    """Leaderboard za Vinjak igricu"""
    st.title("VINJAK IGRICA")
    st.markdown("#### Leaderboard igrača")

    if not manager.config.sheet_igra:
        st.error("❌ Igrica leaderboard nije konfigurijan")
        return

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Osvežite", width="stretch", key="igra_refresh"):
            st.cache_resource.clear()
            st.rerun()

    df = manager.load_data(manager.config.sheet_igra)
    if df.empty:
        st.warning("⚠️ Nema podataka")
        return

    try:
        df = DataProcessor.clean_columns(df)
        logger.info(f"Kolone iz igrice: {list(df.columns)}")

        ime_col = DataProcessor.find_column(df, keywords=["name"], exclude=["timestamp"])
        poeni_col = DataProcessor.find_column(df, keywords=["poeni", "score", "rezultat"])

        if not all([ime_col, poeni_col]):
            st.error("❌ Kolone nisu pronađene!")
            st.info(f"Dostupne kolone: {list(df.columns)}")
            return

        df["poeni_int"] = pd.to_numeric(df[poeni_col], errors="coerce").fillna(0).astype(int)

        leaderboard = df[[ime_col, "poeni_int"]].copy()
        leaderboard.columns = ["Igrač", "Poeni"]
        leaderboard = leaderboard.sort_values("Poeni", ascending=False).reset_index(drop=True)
        leaderboard["Rang"] = range(1, len(leaderboard) + 1)

        st.markdown("---")
        st.subheader("TOP 3 IGRAČA")

        top3 = leaderboard.head(3).copy()
        cols = st.columns(3)
        medals = ["BROJ 1", "BROJ 2", "BROJ 3"]

        for col, medal in zip(cols, medals):
            with col:
                if len(top3) > 0:
                    row = top3.iloc[0]
                    st.metric(medal, row["Igrač"], f"{int(row['Poeni'])} poena")
                    top3 = top3.iloc[1:]
                else:
                    st.metric(medal, "---", "")

        st.markdown("---")
        st.subheader("KOMPLETNA RANGLISTA")
        display_df = leaderboard[["Rang", "Igrač", "Poeni"]].copy()
        st.dataframe(display_df, width="stretch", hide_index=True, height=400)

    except Exception as e:
        logger.error(f"Greška pri obradi igrice: {e}")
        st.error(f"❌ Greška pri obradi: {e}")


def page_galery(manager: GoogleSheetManager) -> None:
    """Galerija oslikanih flase - direktno sa Google Drive-a"""
    st.title("GALERIJA OSLIKANIH FLAŠA VINJAKA")
    st.markdown("#### Sve oslikane flaše sa festivala")

    if not manager.config.drive_slike_id:
        st.error("❌ Google Drive folder nije konfiguriran")
        return

    try:
        creds = service_account.Credentials.from_service_account_info(
            manager.config.credentials,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
        import io

        service = build("drive", "v3", credentials=creds)

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
            st.info("Nema slika u Google Drive folderu")
            return

        files = sorted(files, key=lambda x: x["name"])

        st.subheader(f"{len(files)} Oslikanih Flaša Vinjaka")

        cols = st.columns(3)
        for idx, file in enumerate(files):
            col = cols[idx % 3]
            with col:
                try:
                    request = service.files().get_media(fileId=file["id"])
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False

                    while not done:
                        status, done = downloader.next_chunk()

                    fh.seek(0)

                    st.image(fh, width=300)

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
    setup_page_config()
    setup_custom_css()

    config = load_configuration()
    if not config.is_valid():
        st.error("❌ Kredencijali nisu dostupni!")
        st.info("Postavite GOOGLE_CREDENTIALS_JSON environment varijablu")
        st.stop()

    manager = GoogleSheetManager(config)

    # NAVBAR
    st.markdown(
        '<div class="navbar"><div class="navbar-title">🍇 VINJAK FESTIVAL</div></div>',
        unsafe_allow_html=True,
    )

    # NAV DUGMIĆI
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("Vinjaklija", use_container_width=True, key="nav_vinjaklija"):
            st.session_state.page = "Vinjaklija"
    with col2:
        if st.button("Ispovedaonica", use_container_width=True, key="nav_ispovedaonica"):
            st.session_state.page = "Ispovedaonica"
    with col3:
        if st.button("Sklekovi", use_container_width=True, key="nav_sklekovi"):
            st.session_state.page = "Sklekovi"
    with col4:
        if st.button("Igrica", use_container_width=True, key="nav_igrica"):
            st.session_state.page = "Igrica"
    with col5:
        if st.button("Galerija", use_container_width=True, key="nav_galerija"):
            st.session_state.page = "Galerija"

    if "page" not in st.session_state:
        st.session_state.page = "Vinjaklija"

    st.markdown('<div class="content-wrapper">', unsafe_allow_html=True)

    if st.session_state.page == "Vinjaklija":
        page_home(manager)
    elif st.session_state.page == "Ispovedaonica":
        page_price(manager)
    elif st.session_state.page == "Sklekovi":
        page_sklekovi(manager)
    elif st.session_state.page == "Igrica":
        page_igra(manager)
    elif st.session_state.page == "Galerija":
        page_galery(manager)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    refresh_interval = st.slider(
        "Osvežavanje (sekundi)", min_value=5, max_value=120, value=30, step=5, key="refresh"
    )

    now = datetime.now().strftime("%H:%M:%S")
    st.caption(f"⏰ {now} | Sledeće: ~{refresh_interval}s")

    time.sleep(refresh_interval)
    st.rerun()


if __name__ == "__main__":
    main()
