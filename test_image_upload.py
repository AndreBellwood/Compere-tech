import os
import tempfile
from PIL import Image, ImageDraw
from services.document_service import extract_document_text, extract_image_text, extract_document_clues


def create_test_image(text: str, filename: str) -> str:
    """Creates a clear image containing engineering text for testing OCR/Vision."""
    img = Image.new("RGB", (800, 300), color="white")
    draw = ImageDraw.Draw(img)
    
    y = 30
    for line in text.split("\n"):
        draw.text((30, y), line, fill="black")
        y += 35

    img.save(filename)
    return filename


def test_image_extraction():
    print("=== TEST: Image Document Text Extraction ===")
    with tempfile.TemporaryDirectory() as tmp_dir:
        img_path = os.path.join(tmp_dir, "spec_schedule.png")
        sample_spec = (
            "Apex Consulting Engineers - Project Metro Center\n"
            "AHU-01 Technical Specification\n"
            "Supply Airflow: 5300 l/s\n"
            "Total Cooling Capacity: 56.4 kW\n"
            "External Static Pressure: 250 Pa"
        )
        create_test_image(sample_spec, img_path)
        assert os.path.exists(img_path), "Test image must exist"

        print(f"Extracting document text from {img_path}...")
        extracted_text = extract_document_text(img_path)
        print("Extracted Text Preview:")
        print(extracted_text[:300])

        assert len(extracted_text.strip()) > 0, "Extracted text should not be empty"
        assert "56.4" in extracted_text or "5300" in extracted_text or "AHU" in extracted_text or "CRC" in extracted_text, \
            "Key engineering parameters must be present in OCR text"

        clues = extract_document_clues(extracted_text, "spec_schedule.png")
        print("Extracted Clues:", clues)
        print("[PASS] Image text extraction successfully validated!")


if __name__ == "__main__":
    test_image_extraction()
