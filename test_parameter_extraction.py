import os
import re
import fitz
from services.document_service import extract_document_text
from services.ai_service import extract_document_parameters
from services.report_service import generate_extraction_pdf_report


def test_extraction_pdf_generation():
    print("=== TEST 1: PDF Generation for Parameter Schedule ===")
    mock_spec_data = {
        "project_name": "METROPOLITAN CENTER: HVAC UPGRADES",
        "document_type": "Specification",
        "document_title": "Part 5 - Detail Specifications HVAC",
        "entity_name": "Apex Consulting Engineers",
        "reference_number": "METRO-SPEC-01",
        "executive_summary": (
            "**Document Overview:** Mechanical engineering specification for AHU equipment.\n"
            "**Salient HVAC Duties:** Total cooling duty of 56.4 kW at 5,300 l/s airflow with 250 Pa ESP.\n"
            "**Demarcation:** All equipment must comply with ASHRAE and ISO standards."
        ),
        "scope_table": [
            {
                "Parameter": "Scope of Supply",
                "Value": "Supply and delivery to site",
                "Notes": "By mechanical contractor"
            },
            {
                "Parameter": "Electrical Supply",
                "Value": "400V, 3Ph, 50Hz isolator",
                "Notes": "By electrical contractor"
            }
        ],
        "units": [
            {
                "unit_name": "Unit 1: AHU-01 Primary Air Handling Unit",
                "parameters": [
                    {
                        "Parameter": "Supply Airflow Rate",
                        "Value": "5,300 l/s (19,080 m³/h)",
                        "Notes": "Peak cooling condition"
                    },
                    {
                        "Parameter": "External Static Pressure (ESP)",
                        "Value": "250 Pa",
                        "Notes": "Medium pressure distribution"
                    },
                    {
                        "Parameter": "Total Cooling Capacity",
                        "Value": "56.4 kW",
                        "Notes": "Chilled water 7/12°C"
                    }
                ],
                "technical_notes": [
                    "Coils to feature copper tubes with epoxy-coated aluminium fins.",
                    "Panels to be 50mm double-skinned polyurethane foam insulation."
                ]
            }
        ]
    }

    os.makedirs("uploads/test", exist_ok=True)
    pdf_path = os.path.join("uploads", "test", "test_extraction_schedule.pdf")
    generate_extraction_pdf_report(pdf_path, mock_spec_data)
    assert os.path.exists(pdf_path), "Extraction PDF should be created"

    doc = fitz.open(pdf_path)
    print(f"Total Pages Generated: {len(doc)}")
    assert len(doc) >= 2, "PDF must have at least 2 pages"

    p1_text = doc[0].get_text()
    assert "Date:" in p1_text, "Page 1 must contain Date stamp"
    assert "Serial:" not in p1_text, "Page 1 must not contain Serial number"
    assert "COMPèRE" in p1_text, "COMPèRE branding must appear on Page 1"
    assert "Technical Parameter Schedule" in p1_text, "Header should indicate Parameter Schedule"
    assert "METROPOLITAN CENTER" in p1_text, "Project name must appear"

    p2_text = doc[1].get_text()
    assert "Serial:" in p2_text, "Page 2 must contain Serial stamp"
    serial_match = re.search(r"Serial:\s*(\d{4}-\d{4})", p2_text)
    assert serial_match, f"Serial on Page 2 must be 8 digits (XXXX-XXXX), got: {p2_text[:300]}"
    assert "." not in serial_match.group(1), f"Serial must not contain a decimal, got: {serial_match.group(1)}"
    print(f"[VERIFIED] Serial found on Page 2: '{serial_match.group(0)}'")

    for page_idx, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        size = span["size"]
                        if text:
                            if page_idx > 0 and ("Serial:" in text or re.search(r"\d{4}-\d{4}", text)):
                                assert round(size) == 8, f"Page {page_idx+1} serial '{text}' should be 8 pt, got {size}"
                            else:
                                assert size >= 9.9, f"Page {page_idx+1} span '{text}' has font size {size} < 10 pt!"

    print("[PASS] PDF Report generation verified: font sizes >= 10 pt, OADate serial valid, layout correct.")


def test_extraction_ai_pipeline():
    print("\n=== TEST 2: Live AI Document Extraction ===")
    spec_path = "Test_Suite/Schedule_Refurbishment for TheSquare.pdf" if os.path.exists("Test_Suite/Schedule_Refurbishment for TheSquare.pdf") else "Test_Suite/Spec1.pdf"
    if not os.path.exists(spec_path):
        print(f"Skipping live AI test: {spec_path} not found")
        return

    spec_text = extract_document_text(spec_path)
    assert len(spec_text) > 100, "Spec text should be non-empty"

    print(f"Running extract_document_parameters on {os.path.basename(spec_path)}...")
    res = extract_document_parameters(spec_text, filename=os.path.basename(spec_path), doc_type_hint="Specification")

    print("Identified Project Name:", res.get("project_name"))
    print("Document Nature:", res.get("document_type"))
    print("Entity Name:", res.get("entity_name"))
    print("Scope rows count:", len(res.get("scope_table", [])))
    print("Units count:", len(res.get("units", [])))

    assert res.get("project_name"), "Project name should be extracted"
    assert res.get("executive_summary"), "Executive summary should be generated"
    assert len(res.get("units", [])) > 0, "At least one equipment unit should be extracted"

    unit0 = res["units"][0]
    print(f"First Unit: {unit0.get('unit_name')}, Parameters: {len(unit0.get('parameters', []))}")
    assert len(unit0.get("parameters", [])) > 0, "Parameters should be extracted for unit"

    live_pdf_path = os.path.join("uploads", "test", "test_live_extraction.pdf")
    generate_extraction_pdf_report(live_pdf_path, res)
    assert os.path.exists(live_pdf_path), "Live extraction PDF should be created"
    print(f"[PASS] Successfully generated PDF from live extraction: {live_pdf_path}")


if __name__ == "__main__":
    test_extraction_pdf_generation()
    test_extraction_ai_pipeline()
    print("\nALL STANDALONE EXTRACTION TESTS PASSED!")

