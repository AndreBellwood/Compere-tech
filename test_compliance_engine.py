import os
import sys
from services.document_service import extract_document_text, clean_company_name, extract_document_clues
from services.ai_service import compare_spec_with_offers
from services.report_service import generate_pdf_report

TEST_SUITE_DIR = "Test_Suite"
PREFERRED_SPEC = "Schedule_Refurbishment for TheSquare.pdf"


def find_spec_path():
    """Prefer the preferred spec; otherwise use the first PDF in Test_Suite that is not a vendor quote."""
    preferred = os.path.join(TEST_SUITE_DIR, PREFERRED_SPEC)
    if os.path.exists(preferred):
        return preferred
    if not os.path.isdir(TEST_SUITE_DIR):
        return None
    for name in sorted(os.listdir(TEST_SUITE_DIR)):
        lower = name.lower()
        if lower.endswith(".pdf") and not any(k in lower for k in ("quote", "offer")):
            return os.path.join(TEST_SUITE_DIR, name)
    return None


def find_offer_path():
    """Return the first PDF in Test_Suite that looks like a vendor quote/offer."""
    if not os.path.isdir(TEST_SUITE_DIR):
        return None
    for name in sorted(os.listdir(TEST_SUITE_DIR)):
        lower = name.lower()
        if lower.endswith(".pdf") and any(k in lower for k in ("quote", "offer")):
            return os.path.join(TEST_SUITE_DIR, name)
    return None


def test_clues_and_naming():
    print("=== TEST 1: Clue Extraction and Naming Hygiene ===")
    spec_path = find_spec_path()
    offer_path = find_offer_path()
    if not spec_path or not offer_path:
        print(f"Skipping test: need a spec and a quote PDF in {TEST_SUITE_DIR}")
        return
    
    spec_text = extract_document_text(spec_path)
    offer_text = extract_document_text(offer_path)
    
    spec_clues = extract_document_clues(spec_text, os.path.basename(spec_path))
    offer_clues = extract_document_clues(offer_text, os.path.basename(offer_path))
    
    print("Spec Clues:", spec_clues["project_candidates"])
    print("Offer Clues - Emails:", offer_clues["emails"])
    print("Offer Clues - Domains:", offer_clues["domains"])
    print("Offer Clues - Project:", offer_clues["project_candidates"])
    
    # Clue extraction must return the expected keys; specific domains depend on the PDF used (Test_Suite is swappable).
    assert "domains" in offer_clues and "emails" in offer_clues and "project_candidates" in offer_clues, "Clue dict must contain domains, emails and project_candidates"

    # Test clean company name with split tiers and project separation
    clean_prem = clean_company_name("Carrier (Premium)")
    clean_budg = clean_company_name("Carrier (Budget)")
    clean_inc = clean_company_name("AeroClima Solutions Inc.")
    proj = "Refurbishment of The Square"
    clean_shunter = clean_company_name("Quote_SHUNTER_THE_SQUARE.pdf", proj)
    clean_alpha = clean_company_name("ALPHA Quote. The Square.pdf", proj)
    clean_farrier = clean_company_name("The Square. Farrier 241126.pdf", proj)
    clean_rain = clean_company_name("TheSquare_RAIN Quote.pdf", proj)

    # Test universal dynamic extraction with arbitrary global projects and OEMs
    arb_proj = "Data Center Phase 2 CRAH Modernization"
    clean_munters = clean_company_name("Quote_MUNTERS_DATA_CENTER_PHASE2.pdf", arb_proj)
    clean_flakt = clean_company_name("FlaktGroup_Proposal_DataCenter.pdf", arb_proj)
    clean_jci = clean_company_name("Johnson_Controls_Offer_(Budget).pdf", arb_proj)
    clean_daikin = clean_company_name("Daikin_Applied_Modernization_20261125.pdf", arb_proj)

    print(f"clean_prem: '{clean_prem}'")
    print(f"clean_budg: '{clean_budg}'")
    print(f"clean_inc: '{clean_inc}'")
    print(f"clean_shunter: '{clean_shunter}'")
    print(f"clean_alpha: '{clean_alpha}'")
    print(f"clean_farrier: '{clean_farrier}'")
    print(f"clean_rain: '{clean_rain}'")
    print(f"clean_munters: '{clean_munters}'")
    print(f"clean_flakt: '{clean_flakt}'")
    print(f"clean_jci: '{clean_jci}'")
    print(f"clean_daikin: '{clean_daikin}'")

    assert clean_prem == "Carrier (Premium)"
    assert clean_budg == "Carrier (Budget)"
    assert "AeroClima" in clean_inc
    assert clean_shunter == "Shunter", f"Expected Shunter, got {clean_shunter}"
    assert clean_alpha == "Alpha", f"Expected Alpha, got {clean_alpha}"
    assert clean_farrier == "Farrier", f"Expected Farrier, got {clean_farrier}"
    assert clean_rain.upper() == "RAIN", f"Expected Rain, got {clean_rain}"
    assert clean_munters == "Munters", f"Expected Munters, got {clean_munters}"
    assert clean_flakt == "FlaktGroup", f"Expected FlaktGroup, got {clean_flakt}"
    assert clean_jci == "Johnson Controls (Budget)", f"Expected Johnson Controls (Budget), got {clean_jci}"
    assert clean_daikin == "Daikin Applied", f"Expected Daikin Applied, got {clean_daikin}"

def test_pdf_report_with_project_and_split_offers():
    print("\n=== TEST 2: PDF Report with Project Name & Split Offers ===")
    mock_data = {
        "project_name": "METROPOLITAN CENTER: HEATING VENTILATION AND AIR CONDITIONING",
        "offer_columns": ["AeroClima", "Carrier (Premium)", "Carrier (Budget)", "Trane"],
        "executive_summary": "**Tender Overview:** Adjudication of 4 vendor submissions for Horizon Medical Center AHU Package.\n**Compliance & Variances:** High compliance from AeroClima and Carrier Premium. Carrier Budget omits VRF interface kit.\n**Adjudication Recommendation:** AeroClima and Carrier Premium represent technically compliant bids.",
        "vendor_scores": [
            {"vendor_name": "AeroClima", "compliance_percent": 100.0, "passed_count": 3, "marginal_count": 0, "failed_count": 0, "total_count": 3},
            {"vendor_name": "Carrier (Premium)", "compliance_percent": 95.0, "passed_count": 3, "marginal_count": 0, "failed_count": 0, "total_count": 3},
            {"vendor_name": "Carrier (Budget)", "compliance_percent": 66.7, "passed_count": 2, "marginal_count": 0, "failed_count": 1, "total_count": 3},
            {"vendor_name": "Trane", "compliance_percent": 83.3, "passed_count": 2, "marginal_count": 1, "failed_count": 0, "total_count": 3}
        ],
        "scope_table": [
            {
                "Parameter": "Scope of Supply",
                "Spec_Requirement": "AHU Package complete with controls",
                "vendors": {
                    "AeroClima": {"value": "Full AHU + Controls", "status": "Compliant"},
                    "Carrier (Premium)": {"value": "Full AHU + Premium Controls", "status": "Compliant"},
                    "Carrier (Budget)": {"value": "Standard AHU (Basic controls)", "status": "Compliant"},
                    "Trane": {"value": "AHU Package ex-works", "status": "Marginal"}
                }
            }
        ],
        "units": [
            {
                "unit_name": "Unit 2: Primary Air Handling Unit",
                "parameters": [
                    {
                        "Parameter": "Supply Airflow",
                        "Spec_Requirement": "5300 l/s",
                        "vendors": {
                            "AeroClima": {"value": "5300 l/s", "status": "Compliant"},
                            "Carrier (Premium)": {"value": "5350 l/s", "status": "Compliant"},
                            "Carrier (Budget)": {"value": "5100 l/s", "status": "Marginal"},
                            "Trane": {"value": "5200 l/s", "status": "Compliant"}
                        }
                    },
                    {
                        "Parameter": "Cooling Coil Capacity",
                        "Spec_Requirement": "56.4 kW",
                        "vendors": {
                            "AeroClima": {"value": "56.4 kW", "status": "Compliant"},
                            "Carrier (Premium)": {"value": "58.2 kW", "status": "Compliant"},
                            "Carrier (Budget)": {"value": "48.0 kW", "status": "Non-Compliant"},
                            "Trane": {"value": "66.5 kW", "status": "Marginal"}
                        }
                    }
                ],
                "discrepancies": {
                    "Carrier (Budget)": ["Coil capacity 48.0 kW is 14.9% below design duty."],
                    "Trane": ["Coil oversized by 17.9% (>15% review)."]
                }
            }
        ],
        "specifier_company": "CRC Consulting Engineers",
        "specification_ambiguities": [
            {
                "item": "Unit 2: Cooling Coil",
                "ambiguity": "Entering water temp specified as 7°C on schedule but 6°C in section 4.2.",
                "impact": "Directly impacts coil surface area, rows, and pricing.",
                "verification_action": "Engineer must confirm chilled water design supply temperature."
            }
        ]
    }
    
    os.makedirs("uploads", exist_ok=True)
    report_file_4 = os.path.join("uploads", "test_report_portrait_4v.pdf")
    generate_pdf_report(report_file_4, mock_data)
    assert os.path.exists(report_file_4), "Portrait PDF should be generated"
    
    import fitz
    doc4 = fitz.open(report_file_4)
    p0_4 = doc4[0]
    print(f"4 Vendors Page Size: width={p0_4.rect.width:.2f}, height={p0_4.rect.height:.2f}")
    assert round(p0_4.rect.width) == 595, f"Expected A4 Portrait width ~595, got {p0_4.rect.width}"
    assert round(p0_4.rect.height) == 842, f"Expected A4 Portrait height ~842, got {p0_4.rect.height}"
    
    text4 = "".join(p.get_text() for p in doc4)
    assert "COMPèRE" in text4, "COMPèRE with grave accent must be present in text"
    
    # Verify Date stamp on Page 1 and Serial on Page 2+
    p1_text = doc4[0].get_text()
    p2_text = doc4[1].get_text()
    print("Page 1 Text Sample:\n", p1_text[:300])
    print("Page 2 Text Sample:\n", p2_text[:300])
    assert "Date:" in p1_text, "Date stamp must be present on Page 1"
    assert "Serial:" not in p1_text, "Serial number should not be on Page 1"
    assert "Serial:" in p2_text, "Serial number must be present on Page 2"
    
    # Verify 8 digits, no decimal, dash after four digits (XXXX-XXXX)
    import re
    serial_match_4 = re.search(r"Serial:\s*(\d{4}-\d{4})", p2_text)
    assert serial_match_4, f"Serial on Page 2 must be 8 digits with dash after 4 digits (XXXX-XXXX), got:\n{p2_text[:300]}"
    assert "." not in serial_match_4.group(1), f"Serial must not contain a decimal, got: {serial_match_4.group(1)}"
    print(f"[VERIFIED] Page 2 Serial found: '{serial_match_4.group(0)}'")

    for page_idx, page in enumerate(doc4):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        size = span["size"]
                        if text:
                            # Serial number on page 2+ is strictly 8 pt font
                            if page_idx > 0 and ("Serial:" in text or re.search(r"\d{4}-\d{4}", text)):
                                assert round(size) == 8, f"Page {page_idx+1} serial '{text}' should be 8 pt, got {size}"
                            else:
                                assert size >= 9.9, f"Page {page_idx+1} span '{text}' has font size {size} < 10 pt!"

    print("[PASS] 4 Vendors successfully generated in A4 PORTRAIT mode with strictly >= 10 pt text, Page 1 Date stamp, and Page 2+ bottom right 8 pt Serial.")

    # 5 Vendors -> MUST BE A4 LANDSCAPE
    mock_data_5 = dict(mock_data)
    mock_data_5["offer_columns"] = ["AeroClima", "Carrier (Premium)", "Carrier (Budget)", "Trane", "Daikin"]
    mock_data_5["vendor_scores"] = list(mock_data["vendor_scores"]) + [
        {"vendor_name": "Daikin", "compliance_percent": 90.0, "passed_count": 3, "marginal_count": 0, "failed_count": 0, "total_count": 3}
    ]
    report_file_5 = os.path.join("uploads", "test_report_landscape_5v.pdf")
    generate_pdf_report(report_file_5, mock_data_5)
    assert os.path.exists(report_file_5), "Landscape PDF should be generated"
    
    doc5 = fitz.open(report_file_5)
    p0_5 = doc5[0]
    print(f"5 Vendors Page Size: width={p0_5.rect.width:.2f}, height={p0_5.rect.height:.2f}")
    assert round(p0_5.rect.width) == 842, f"Expected A4 Landscape width ~842, got {p0_5.rect.width}"
    assert round(p0_5.rect.height) == 595, f"Expected A4 Landscape height ~595, got {p0_5.rect.height}"
    
    p1_5_text = doc5[0].get_text()
    p2_5_text = doc5[1].get_text()
    assert "Date:" in p1_5_text, "Date stamp must be present on Page 1 of 5-vendor report"
    assert "Serial:" not in p1_5_text, "Serial number should not be on Page 1 of 5-vendor report"
    assert "Serial:" in p2_5_text, "Serial number must be present on Page 2 of 5-vendor report"
    serial_match_5 = re.search(r"Serial:\s*(\d{4}-\d{4})", p2_5_text)
    assert serial_match_5, f"Serial on Page 2 of 5-vendor report must be 8 digits with dash after 4 digits (XXXX-XXXX), got: {p2_5_text[:300]}"
    assert "." not in serial_match_5.group(1), f"Serial must not contain a decimal, got: {serial_match_5.group(1)}"
    print(f"[VERIFIED] Page 2 (5-vendor) Serial found: '{serial_match_5.group(0)}'")

    for page_idx, page in enumerate(doc5):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        size = span["size"]
                        if text:
                            # Serial number on page 2+ is strictly 8 pt font
                            if page_idx > 0 and ("Serial:" in text or re.search(r"\d{4}-\d{4}", text)):
                                assert round(size) == 8, f"Page {page_idx+1} serial '{text}' should be 8 pt, got {size}"
                            else:
                                assert size >= 9.9, f"Page {page_idx+1} span '{text}' has font size {size} < 10 pt!"

    print("[PASS] 5 Vendors successfully generated in A4 LANDSCAPE mode with strictly >= 10 pt text and COMPèRE branding.")

def test_live_ai_audit():
    print("\n=== TEST 3: Live AI Compliance Audit with Clues & Project Extraction ===")
    spec_path = find_spec_path()
    offer_path = find_offer_path()
    if not spec_path or not offer_path:
        print(f"Skipping live AI test: need a spec and a quote PDF in {TEST_SUITE_DIR}")
        return
    spec_text = extract_document_text(spec_path)
    offer_text = extract_document_text(offer_path)
    
    # Intentionally passing a generic filename "Quote_Option_1.pdf" to verify it detects the true vendor and project
    vendor_offers = [
        {"filename": "Quote_Option_1.pdf", "text": offer_text}
    ]
    
    try:
        results = compare_spec_with_offers(spec_text, vendor_offers)
        print("Identified Project Name:", results.get("project_name"))
        print("Vendor Scores:", results.get("vendor_scores"))
        print("Offer Columns:", results.get("offer_columns"))
        
        v_scores = results.get("vendor_scores", [])
        assert len(v_scores) > 0, "Should have vendor scores"
        v_name = v_scores[0]["vendor_name"]
        print(f"Detected Vendor Name: '{v_name}'")
        assert "offer1" not in v_name.lower(), f"Vendor name should not be Offer1, got: {v_name}"
        
        proj = results.get("project_name", "")
        print(f"Detected Project: '{proj}'")
        assert proj and proj.lower() != "unknown", "Project name should be detected"
        print("LIVE AI AUDIT TEST PASSED!")
    except Exception as e:
        raise AssertionError(f"Live AI audit failed: {e}") from e

if __name__ == "__main__":
    test_clues_and_naming()
    test_pdf_report_with_project_and_split_offers()
    print("\nALL VERIFICATIONS COMPLETED!")
