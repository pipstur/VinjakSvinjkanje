import os
import time
from rembg import remove
from PIL import Image, ImageEnhance
import io

INPUT_DIR = "slike/unedited"
OUTPUT_DIR = "slike/flase"
PIXEL_SIZE = 24
NUM_COLORS = 256
CONTRAST_FACTOR = 1.2
COLOR_FACTOR = 1.2
CHECK_INTERVAL = 60  # sekunde

os.makedirs(OUTPUT_DIR, exist_ok=True)


def process_image(file_path, output_dir):
    file_name = os.path.basename(file_path)
    output_path = os.path.join(output_dir, os.path.splitext(file_name)[0] + "_pixel.png")

    # --- Uklanjanje pozadine ---
    with open(file_path, "rb") as f:
        input_data = f.read()
    output_data = remove(input_data)
    img = Image.open(io.BytesIO(output_data)).convert("RGBA")

    # --- Automatski crop transparentnih ivica ---
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    # --- Pikselizacija ---
    small = img.resize(
        (max(1, img.width // PIXEL_SIZE), max(1, img.height // PIXEL_SIZE)), resample=Image.NEAREST
    )
    pixelized = small.resize(img.size, Image.NEAREST)

    # --- Podesi kontrast i boje ---
    pixelized = ImageEnhance.Contrast(pixelized).enhance(CONTRAST_FACTOR)
    pixelized = ImageEnhance.Color(pixelized).enhance(COLOR_FACTOR)

    # --- Konverzija u 8-bit ---
    pixelized = pixelized.convert("P", palette=Image.ADAPTIVE, colors=NUM_COLORS)

    # --- Sačuvaj rezultat ---
    pixelized.save(output_path)
    print(f"Gotovo! {file_name} -> {output_path}")


def get_files_with_mtime(folder):
    """Vrati dict {file_path: mtime} za sve slike u folderu"""
    supported_ext = [".png", ".jpg", ".jpeg"]
    files = {}
    for f in os.listdir(folder):
        if os.path.splitext(f)[1].lower() in supported_ext:
            path = os.path.join(folder, f)
            files[path] = os.path.getmtime(path)
    return files


def main():
    processed_files = {}  # čuva {file_path: last_mtime} da zna šta je promenjeno

    while True:
        files = get_files_with_mtime(INPUT_DIR)
        for path, mtime in files.items():
            # Ako fajl nije obrađen ili je promenjen, obradi ga
            if path not in processed_files or processed_files[path] < mtime:
                process_image(path, OUTPUT_DIR)
                processed_files[path] = mtime

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
