import json
import re
from openai import OpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from services.document_service import clean_company_name, extract_document_clues

def compare_spec_with_offers(spec_text: str, vendor_offers: list[dict]) -> dict:
    """
    Audits one or more vendor submissions against an engineering specification.
    Identifies common project name, extracts true vendor names from document clues,
    and splits multi-tier submissions (e.g. Premium vs Budget) into separate columns.
    
    vendor_offers is a list of dicts: [{"vendor_name": "...", "text": "...", "filename": "..."}]
    """
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    
    spec_clues = extract_document_clues(spec_text, "Specification")
    
    offers_prompt_section = ""
    candidate_clues_summary = []
    
    for idx, v in enumerate(vendor_offers, start=1):
        filename = v.get("filename", v.get("vendor_name", f"Submission_{idx}"))
        v_text = v.get("text", "")
        clues = extract_document_clues(v_text, filename)
        
        email_str = ", ".join(clues["emails"]) if clues["emails"] else "None found"
        domain_str = ", ".join(clues["domains"]) if clues["domains"] else "None"
        ref_str = ", ".join(clues["quote_refs"]) if clues["quote_refs"] else "None"
        tier_str = ", ".join(clues["tier_hints"]) if clues["tier_hints"] else "Single standard offer"
        proj_str = ", ".join(clues["project_candidates"][:2]) if clues["project_candidates"] else "None explicit"

        candidate_clues_summary.append(
            f"Submission {idx} (File: {filename}):\n"
            f"  • Emails: {email_str} (Domains: {domain_str})\n"
            f"  • Quote References: {ref_str}\n"
            f"  • Project Indicators: {proj_str}\n"
            f"  • Potential Offer Tiers: {tier_str}\n"
            f"  • Header Preview:\n{clues['header_snippet'][:250]}"
        )

        offers_prompt_section += f"\n--- VENDOR SUBMISSION {idx} (File: {filename}) ---\n{v_text}\n"

    clues_text = "\n\n".join(candidate_clues_summary)
    spec_proj_hints = ", ".join(spec_clues["project_candidates"][:3]) if spec_clues["project_candidates"] else "Check spec text"

    user_prompt = f"""
You are an independent Principal HVAC Consulting Engineer conducting a professional technical compliance audit.

Objective:
Audit the Vendor Submission(s) against the Engineering Specification. Normalize engineering units naturally (e.g., l/s to m³/s, kW, Pa, °C DB/WB) to allow clean side-by-side comparison.

Adjudication Intelligence Requirements:
1. ACCURATE PROJECT NAME IDENTIFICATION:
   - Identify the overarching Project Name common across the specification and vendor quotations (e.g., "SASOL Phase 1 Expansion", "Msukligwe Ermelo", "DATA HALL 1 & UPS ROOM - CRAH UPGRADE").
   - Spec Project Hints: {spec_proj_hints}
   - Set "project_name" at the top level of the JSON.

2. IN-DOCUMENT VENDOR IDENTITY EXTRACTION:
   - DO NOT rely on arbitrary uploaded file names (e.g. 'Offer1.pdf', 'quote_1.pdf', or generic titles).
   - Use internal document clues (document letterheads, logos, email domain names, signature blocks, quotation references) to identify the real company name (e.g., "ThermOpac", "Carrier", "Trane", "Daikin", "AirCraft", "ClimaCore").
   - Distinguish the equipment vendor/manufacturer from the client or engineer (e.g. client may be Sasol or CRC Eng; vendor is the quoting entity).

3. MULTI-VENDOR & SPLIT OFFER COLUMNS:
   - Each vendor offer MUST have its own column in the audit matrix.
   - IF A SINGLE VENDOR SUBMITS A PREMIUM OFFER AS WELL AS A BUDGET OFFER (or Option 1 vs Option 2, Inverter vs Fixed-speed, Base vs Alternative), SPLIT THAT VENDOR'S SUBMISSIONS INTO TWO COLUMNS!
     Example column labels:
     • "Carrier (Premium)" and "Carrier (Budget)"
     • "ThermOpac (Option 1)" and "ThermOpac (Option 2)"
   - If a vendor submits only a single standard offer, use their clean company name (e.g., "Trane", "Daikin").
   - Use these exact column names consistently across "offer_columns", "scope_table", "units", and "discrepancies".

4. EXECUTIVE SUMMARY READABILITY:
   - Format the 'executive_summary' into short, readable paragraphs (3-4 lines each) with bold headings:
     - **Tender Overview:** High-level summary of scope, project, and bids received.
     - **Compliance & Variances:** Key thermal/mechanical deviations, capacity deficits, or exclusions.
     - **Adjudication Recommendation:** Concise conclusion and recommendation.
   - Keep total executive summary under 140 words.

5. CONCISE NUMERICAL REQUIREMENTS:
   - In parameter grids, limit 'Spec_Requirement' strictly to a concise number and unit of measurement (e.g., '5300 l/s', '1000 Pa', '56.4 kW', '22.0 °C DB').
   - In each offer column, provide the matching offered number and unit. All descriptive remarks belong in 'discrepancies'.

6. STATUS CLASSIFICATIONS:
   - 'Compliant': Satisfies specified duty within engineering tolerance (±5%).
   - 'Marginal': Feature listed only as optional add-on, oversizing >15%, delivery to hub only, or off-loading omitted by OEM.
   - 'Non-Compliant': Substantive deficit (< -5%), invalid design conditions, or missing core components.

--- EXTRACTED METADATA CLUES ---
{clues_text}

--- SPECIFICATION TEXT ---
{spec_text}

{offers_prompt_section}

Return your evaluation strictly as a valid JSON object matching this structure:
{{
  "project_name": "Accurately Identified Project Name",
  "offer_columns": ["Column 1", "Column 2"],
  "executive_summary": "Objective executive summary comparing vendor submissions against specification requirements.",
  "scope_table": [
    {{
      "Parameter": "Scope of Supply",
      "Spec_Requirement": "Detailed requirement from spec",
      "vendors": {{
        "Column_Name": {{
          "value": "Brief offered scope",
          "status": "Compliant / Marginal / Non-Compliant"
        }}
      }}
    }}
  ],
  "units": [
    {{
      "unit_name": "Unit 1: [Equipment Tag and Duty]",
      "parameters": [
        {{
          "Parameter": "Supply Airflow",
          "Spec_Requirement": "3.30 m³/s",
          "vendors": {{
            "Column_Name": {{
              "value": "3.33 m³/s",
              "status": "Compliant"
            }}
          }}
        }}
      ],
      "discrepancies": {{
        "Column_Name": [
          "Factual technical note regarding variances, options, or unaddressed items."
        ]
      }}
    }}
  ]
}}
"""
    
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.1
        )
        
        # Isolate the text directly by checking structural layout states
        if hasattr(response, 'choices'):
            choices_list = response.choices
            if isinstance(choices_list, list) and len(choices_list) > 0:
                item = choices_list[0]
                if hasattr(item, 'message'):
                    raw_content = item.message.content
                elif isinstance(item, dict) and 'message' in item:
                    msg = item['message']
                    raw_content = msg.get('content', str(msg)) if isinstance(msg, dict) else str(msg)
                else:
                    raw_content = getattr(item, 'text', str(item))
            else:
                raw_content = response.choices.message.content
        elif isinstance(response, list) and len(response) > 0:
            item = response[0]
            if hasattr(item, 'message'):
                raw_content = item.message.content
            else:
                raw_content = item.get('message', {}).get('content', str(item))
        else:
            raw_content = str(response)
            
    except Exception as e:
        raise Exception(f"API Interface Exception: {str(e)}")

    try:
        data = json.loads(raw_content)
    except Exception:
        # Isolate the core JSON matrix strings using a strict regex boundary locator
        json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
    # Validate / Fallback for project_name
    proj = data.get("project_name")
    if not proj or str(proj).strip().lower() in ["unknown", "accurately identified project name", "project", "none"]:
        candidate = None
        if spec_clues.get("project_candidates"):
            candidate = spec_clues["project_candidates"][0]
        else:
            for v in vendor_offers:
                v_clues = extract_document_clues(v.get("text", ""))
                if v_clues.get("project_candidates"):
                    candidate = v_clues["project_candidates"][0]
                    break
        data["project_name"] = candidate or "HVAC Engineering Project"
    else:
        data["project_name"] = str(proj).strip()

    # Discover and sanitize offer column names
    raw_columns = data.get("offer_columns", [])
    clean_columns = [clean_company_name(c) for c in raw_columns if c]
    
    # Calculate automated percentage compliance scores for each identified offer column
    calculate_vendor_scores(data, clean_columns)
    return data


def calculate_vendor_scores(data: dict, vendor_names: list):
    """
    Calculates numerical % compliance scores for each vendor / offer column across evaluated parameters.
    Score = (Passed + 0.5 * Marginal) / Total * 100
    """
    all_vendors = list(vendor_names)
    
    # Ensure all vendors appearing in units are included
    for unit in data.get("units", []):
        for param in unit.get("parameters", []):
            for vk in param.get("vendors", {}).keys():
                c_vk = clean_company_name(vk)
                if c_vk and c_vk not in all_vendors:
                    all_vendors.append(c_vk)

    for row in data.get("scope_table", []):
        for vk in row.get("vendors", {}).keys():
            c_vk = clean_company_name(vk)
            if c_vk and c_vk not in all_vendors:
                all_vendors.append(c_vk)

    scores = {v: {"passed": 0, "marginal": 0, "failed": 0, "total": 0} for v in all_vendors}

    # Tally from units
    for unit in data.get("units", []):
        for param in unit.get("parameters", []):
            vendors_dict = param.get("vendors", {})
            for v_name, v_data in vendors_dict.items():
                c_name = clean_company_name(v_name)
                if c_name not in scores:
                    scores[c_name] = {"passed": 0, "marginal": 0, "failed": 0, "total": 0}
                status = str(v_data.get("status", "")).lower()
                scores[c_name]["total"] += 1
                if "marginal" in status or "confirm" in status or "tbc" in status or "option" in status or "oversiz" in status:
                    scores[c_name]["marginal"] += 1
                elif "non" in status or "fail" in status or "reject" in status or "exclud" in status:
                    scores[c_name]["failed"] += 1
                elif "compliant" in status or "pass" in status or "meet" in status:
                    scores[c_name]["passed"] += 1
                else:
                    scores[c_name]["marginal"] += 1

    vendor_summary = []
    for v_name, counts in scores.items():
        total = counts["total"]
        if total > 0:
            pct = round(((counts["passed"] + 0.5 * counts["marginal"]) / total) * 100, 1)
        else:
            pct = 0.0
        vendor_summary.append({
            "vendor_name": v_name,
            "compliance_percent": pct,
            "passed_count": counts["passed"],
            "marginal_count": counts["marginal"],
            "failed_count": counts["failed"],
            "total_count": total
        })

    data["vendor_scores"] = vendor_summary


def compare_spec_with_offer(spec_text: str, offer_text: str) -> dict:
    """Backward compatibility wrapper for single offer analysis."""
    return compare_spec_with_offers(spec_text, [{"vendor_name": "Vendor Offer", "text": offer_text}])


