import os
import json
import re
import importlib
from openai import OpenAI
import config
from services.document_service import clean_company_name, extract_document_clues
from services.currency_service import get_live_rates


def get_ai_client():
    """Dynamically reloads config to pick up runtime updates to API keys/models.
    Returns (client, model_name, provider). For Anthropic, client is an anthropic.Anthropic instance."""
    try:
        importlib.reload(config)
    except Exception:
        pass
    if config.LLM_PROVIDER == "anthropic":
        import anthropic
        # Explicit timeout so a stalled request fails with a clear error instead of hanging indefinitely.
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY or config.LLM_API_KEY, timeout=300.0, max_retries=2)
        return client, config.LLM_MODEL, "anthropic"
    client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL, timeout=180.0, max_retries=2)
    return client, config.LLM_MODEL, "gemini"


MAX_OUTPUT_TOKENS = 32000


def parse_llm_json(raw_content: str) -> dict:
    """Parses a JSON object from an LLM response, tolerating markdown code fences and surrounding text."""
    text = (raw_content or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
    except Exception:
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            raise ValueError(f"LLM response contained no JSON object (length {len(raw_content or '')}): {(raw_content or '')[:300]}")
        try:
            data = json.loads(json_match.group(0))
        except Exception as e:
            raise ValueError(f"LLM response JSON could not be parsed (length {len(raw_content or '')}): {e}") from e
    if not isinstance(data, dict):
        raise ValueError("LLM response JSON was not an object")
    return data


def request_text_completion(client, model_name: str, provider: str, user_prompt: str, temperature: float = 0.1) -> str:
    """Sends a single-turn prompt to the configured provider and returns the response text."""
    if provider == "anthropic":
        # The installed Anthropic SDK rejects the 'temperature' keyword, so it is omitted on this path.
        # Streaming is required by the Anthropic SDK for large max_tokens values (avoids the 10-minute non-streaming guard).
        with client.messages.stream(
            model=model_name,
            max_tokens=MAX_OUTPUT_TOKENS,
            messages=[{"role": "user", "content": user_prompt}]
        ) as stream:
            response = stream.get_final_message()
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise ValueError(f"LLM response was truncated at the {MAX_OUTPUT_TOKENS} token output limit")
        return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")

    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=temperature
    )
    return response.choices[0].message.content


def build_user_preferences_instructions(user_preferences: dict) -> str:
    """Builds explicit LLM instructions based on user-defined limits and preferences."""
    if not user_preferences:
        return ""

    instructions = []
    scope = user_preferences.get("equipment_scope", "")
    if isinstance(scope, list):
        if len(scope) < 7 and len(scope) > 0:
            scope_str = ", ".join(f"'{s}'" for s in scope)
            instructions.append(
                f"USER PREFERENCE - EQUIPMENT SCOPE LIMIT: The audit is strictly limited to the following selected equipment categories: {scope_str}. Only evaluate equipment units matching these designated categories. Omit other equipment types from schedules and scoring."
            )
    elif scope and "Auto-select" not in scope:
        if "10kW capacity" in scope:
            instructions.append(
                "USER PREFERENCE - EQUIPMENT SCOPE LIMIT: Focus exclusively on CHW Units, DX AHUs, Roof-top packages, and hybrid units larger than 10kW capacity. Omit smaller residential units, small splits, or non-HVAC systems."
            )
        elif "smaller than 10kW" in scope:
            instructions.append(
                "USER PREFERENCE - EQUIPMENT SCOPE LIMIT: Focus exclusively on splits, ducted splits, cassettes, and unitary units smaller than 10kW capacity. Omit large central AHUs or heavy central plant equipment."
            )
        else:
            instructions.append(f"USER PREFERENCE - EQUIPMENT SCOPE LIMIT: Filter and limit evaluation to: {scope}.")

    currency = user_preferences.get("preferred_currency", "Document Default")
    if currency and currency != "Document Default":
        rates = get_live_rates()
        curr_rate = rates.get(currency.upper(), 1.0)
        instructions.append(
            f"USER PREFERENCE - CURRENCY CONVERSION: Convert all equipment prices, rates, and costs into '{currency.upper()}' at prevailing daily spot rates. In tables and financial summaries, display the converted amount and the original quoted currency in brackets, e.g., '{currency} XX,XXX [Orig: ZAR/USD XX,XXX]'."
        )

    units_sys = user_preferences.get("preferred_units", "Document Default")
    if units_sys and units_sys != "Document Default":
        if "Imperial" in units_sys:
            instructions.append(
                "USER PREFERENCE - MEASUREMENT UNITS: Present all engineering values normalized in IMPERIAL units (Tons/BTU/h for cooling/heating, CFM for airflow, in.wg for static pressure, °F for DB/WB temperatures, inches for dimensions, lbs for weight)."
            )
        elif "Metric" in units_sys:
            instructions.append(
                "USER PREFERENCE - MEASUREMENT UNITS: Present all engineering values normalized in METRIC (SI) units (kW for cooling/heating, l/s or m³/s for airflow, Pa for static pressure, °C for DB/WB temperatures, mm for dimensions, kg for weight)."
            )
        elif "Asian" in units_sys:
            instructions.append(
                "USER PREFERENCE - MEASUREMENT UNITS: Present all engineering values normalized in ASIAN / REGIONAL units (RT or kcal/h for cooling, m³/h for airflow, mmAq or Pa for static pressure, °C for temperatures)."
            )
        elif "Mixed" in units_sys:
            instructions.append(
                "USER PREFERENCE - MEASUREMENT UNITS: Present all engineering values with DUAL / MIXED units (e.g. '56.4 kW (16.0 TR)', '5,300 l/s (11,230 CFM)', '24°C DB (75.2°F)', '250 Pa (1.0 in.wg)')."
            )

    if instructions:
        return "\n--- APPLIED USER PREFERENCES & LIMITS ---\n" + "\n".join(instructions) + "\n"
    return ""


def _ask_json(client, model_name, provider, prompt: str) -> dict:
    """Runs one small LLM call and returns its parsed JSON object."""
    return parse_llm_json(request_text_completion(client, model_name, provider, prompt))


def run_split_audit(client, model_name, provider, full_prompt, spec_text, clues_text, spec_proj_hints, vendor_id_rule, pref_instructions, offers_prompt_section) -> dict:
    """
    Runs the compliance audit as several small LLM calls instead of one large one, so each response
    returns quickly. Produces the same output shape as the single-call audit:
      - header call: project_name, offer_columns, executive_summary, specification_ambiguities, unit names
      - scope call: scope_table
      - one call per equipment unit: that unit's parameters and discrepancies
    """
    shared_context = f"""
You are an independent Principal HVAC Consulting Engineer conducting a professional technical compliance audit.
Objective: Audit the Vendor Submission(s) against the Engineering Specification. Normalize engineering units naturally (e.g., l/s to m³/s, kW, Pa, °C DB/WB).
{pref_instructions}
{vendor_id_rule}
Use these exact column names consistently. Keep status values to: Compliant, Marginal, or Non-Compliant.

--- EXTRACTED METADATA CLUES ---
{clues_text}

--- SPECIFICATION TEXT ---
{spec_text}

{offers_prompt_section}
"""

    header = _ask_json(client, model_name, provider, shared_context + f"""
TASK: Return ONLY this JSON object (no other text):
{{
  "project_name": "Accurately Identified Project Name (spec hints: {spec_proj_hints})",
  "offer_columns": ["Column 1", "Column 2"],
  "executive_summary": "**Tender Overview:** ... **Compliance & Variances:** ... **Adjudication Recommendation:** ... (under 140 words total)",
  "specification_ambiguities": [
    {{"item": "...", "ambiguity": "...", "impact": "...", "verification_action": "..."}}
  ],
  "unit_names": ["Unit 1: [Equipment Tag and Duty]", "Unit 2: ..."]
}}
""")

    scope = _ask_json(client, model_name, provider, shared_context + """
TASK: Return ONLY this JSON object (no other text) with the scope-of-supply / demarcation comparison:
{
  "scope_table": [
    {
      "Parameter": "Scope of Supply",
      "Spec_Requirement": "Detailed requirement from spec",
      "vendors": {
        "Column_Name": {"value": "Brief offered scope", "status": "Compliant / Marginal / Non-Compliant"}
      }
    }
  ]
}
""")

    units = []
    for unit_name in header.get("unit_names", []) or []:
        unit = _ask_json(client, model_name, provider, shared_context + f"""
TASK: Audit ONLY the equipment unit named "{unit_name}". Return ONLY this JSON object (no other text):
{{
  "unit_name": "{unit_name}",
  "parameters": [
    {{
      "Parameter": "Supply Airflow",
      "Spec_Requirement": "3.30 m³/s",
      "vendors": {{
        "Column_Name": {{"value": "3.33 m³/s", "status": "Compliant"}}
      }}
    }}
  ],
  "discrepancies": {{
    "Column_Name": ["Factual technical note regarding variances, options, or unaddressed items."]
  }}
}}
""")
        units.append(unit)

    data = {
        "project_name": header.get("project_name", ""),
        "offer_columns": header.get("offer_columns", []),
        "executive_summary": header.get("executive_summary", ""),
        "specification_ambiguities": header.get("specification_ambiguities", []),
        "scope_table": scope.get("scope_table", []),
        "units": units,
    }
    return data


def compare_spec_with_offers(spec_text: str, vendor_offers: list[dict], user_preferences: dict = None, specifier_company: str = "") -> dict:
    """
    Audits one or more vendor submissions against an engineering specification.
    Identifies common project name, extracts true vendor names from document clues,
    and splits multi-tier submissions (e.g. Premium vs Budget) into separate columns.
    
    vendor_offers is a list of dicts: [{"vendor_name": "...", "text": "...", "filename": "..."}]
    """
    client, model_name, provider = get_ai_client()
    
    spec_clues = extract_document_clues(spec_text, "Specification")
    
    offers_prompt_section = ""
    candidate_clues_summary = []
    vendor_declarations = []
    
    for idx, v in enumerate(vendor_offers, start=1):
        filename = v.get("filename", v.get("vendor_name", f"Submission_{idx}"))
        v_name = v.get("vendor_name", "").strip()
        v_text = v.get("text", "")
        clues = extract_document_clues(v_text, filename)
        
        email_str = ", ".join(clues["emails"]) if clues["emails"] else "None found"
        domain_str = ", ".join(clues["domains"]) if clues["domains"] else "None"
        ref_str = ", ".join(clues["quote_refs"]) if clues["quote_refs"] else "None"
        tier_str = ", ".join(clues["tier_hints"]) if clues["tier_hints"] else "Single standard offer"
        proj_str = ", ".join(clues["project_candidates"][:2]) if clues["project_candidates"] else "None explicit"

        name_note = ""
        if v_name and v_name != filename:
            name_note = f"  • USER-DECLARED VENDOR COMPANY NAME: '{v_name}' (Authoritative)\n"
            vendor_declarations.append(f"• Submission {idx} ('{filename}') is from: '{v_name}'")

        candidate_clues_summary.append(
            f"Submission {idx} (File: {filename}):\n"
            f"{name_note}"
            f"  • Emails: {email_str} (Domains: {domain_str})\n"
            f"  • Quote References: {ref_str}\n"
            f"  • Project Indicators: {proj_str}\n"
            f"  • Potential Offer Tiers: {tier_str}\n"
            f"  • Header Preview:\n{clues['header_snippet'][:250]}"
        )

        offers_prompt_section += f"\n--- VENDOR SUBMISSION {idx} (File: {filename}) ---\n{v_text}\n"

    clues_text = "\n\n".join(candidate_clues_summary)
    spec_proj_hints = ", ".join(spec_clues["project_candidates"][:3]) if spec_clues["project_candidates"] else "Check spec text"
    pref_instructions = build_user_preferences_instructions(user_preferences)

    specifier_note = f"\n- Specifier / Consulting Engineering Firm: '{specifier_company}' (Consulting Engineer)." if specifier_company else ""
    vendor_decl_str = "\n   ".join(vendor_declarations) if vendor_declarations else ""
    if vendor_decl_str:
        vendor_id_rule = f"""2. AUTHORITATIVE VENDOR IDENTITY & SPECIFIER FIRM:
   {specifier_note}
   - The user has provided authoritative company names for the following submissions:
   {vendor_decl_str}
   - You MUST use these exact vendor company names as the column headers in 'offer_columns' and in all tables, scores, and discrepancies (unless splitting a vendor's offer into Premium vs Budget, in which case use '[Vendor] (Premium)' and '[Vendor] (Budget)')."""
    else:
        vendor_id_rule = f"""2. IN-DOCUMENT VENDOR IDENTITY EXTRACTION:
   {specifier_note}
   - DO NOT rely on arbitrary uploaded file names (e.g. 'Offer1.pdf', 'quote_1.pdf', or generic titles).
   - Use internal document clues (document letterheads, logos, email domain names, signature blocks, quotation references) to identify the real company name (e.g., 'AeroClima', 'Carrier', 'Trane', 'Daikin', 'ApexAir', 'ClimaCore').
   - Distinguish the equipment vendor/manufacturer from the client or engineer."""

    user_prompt = f"""
You are an independent Principal HVAC Consulting Engineer conducting a professional technical compliance audit.

Objective:
Audit the Vendor Submission(s) against the Engineering Specification. Normalize engineering units naturally (e.g., l/s to m³/s, kW, Pa, °C DB/WB) to allow clean side-by-side comparison.
{pref_instructions}
Adjudication Intelligence Requirements:
1. ACCURATE PROJECT NAME IDENTIFICATION:
   - Identify the overarching Project Name common across the specification and vendor quotations (e.g., "Metro Center Central Plant Modernization", "DATA HALL 1 & UPS ROOM - CRAH UPGRADE").
   - Spec Project Hints: {spec_proj_hints}
   - Set "project_name" at the top level of the JSON.

{vendor_id_rule}

3. MULTI-VENDOR & SPLIT OFFER COLUMNS:
   - Each vendor offer MUST have its own column in the audit matrix.
   - IF A SINGLE VENDOR SUBMITS A PREMIUM OFFER AS WELL AS A BUDGET OFFER (or Option 1 vs Option 2, Inverter vs Fixed-speed, Base vs Alternative), SPLIT THAT VENDOR'S SUBMISSIONS INTO TWO COLUMNS!
     Example column labels:
     • "Carrier (Premium)" and "Carrier (Budget)"
     • "AeroClima (Option 1)" and "AeroClima (Option 2)"
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

7. SPECIFICATION AMBIGUITY & HUMAN VERIFICATION FLAGGING:
   - Carefully analyze the specification for ambiguous, contradictory, incomplete, or vague engineering duties (e.g., conflicting fluid temperatures, unspecified static pressure baselines, ambiguous airflow metrics, missing demarcation for electrical starters/VSDs or controls, or missing ambient baselines).
   - Flag every ambiguity in 'specification_ambiguities' so the human engineer can verify or issue a formal addendum.

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
  "specification_ambiguities": [
    {{
      "item": "Affected Equipment Tag or Parameter",
      "ambiguity": "Precise description of the specification ambiguity or conflicting requirement",
      "impact": "Practical impact on equipment sizing, pricing, or compliance",
      "verification_action": "Specific human clarification action required by consulting engineer"
    }}
  ],
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
        raw_content = request_text_completion(client, model_name, provider, user_prompt)
        data = parse_llm_json(raw_content)
    except Exception as e:
        raise Exception(f"API Interface Exception: {str(e)}")

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

    if specifier_company:
        data["specifier_company"] = specifier_company.strip()

    # Remap columns and tables to user-confirmed vendor names if declared
    vendor_override_map = {}
    for v in vendor_offers:
        vn = v.get("vendor_name", "").strip()
        fn = v.get("filename", "").strip()
        if vn and fn and vn != fn:
            vendor_override_map[fn] = vn
            vendor_override_map[os.path.splitext(fn)[0]] = vn

    if vendor_override_map:
        def remap_col(c):
            clean_c = clean_company_name(c)
            for old_k, new_k in vendor_override_map.items():
                if old_k.lower() in clean_c.lower():
                    if "(" in clean_c and ")" in clean_c:
                        tier = clean_c[clean_c.find("("):clean_c.rfind(")")+1]
                        return f"{new_k} {tier}".strip()
                    return new_k
            return clean_c

        if "offer_columns" in data and isinstance(data["offer_columns"], list):
            data["offer_columns"] = [remap_col(c) for c in data["offer_columns"]]
        if "scope_table" in data and isinstance(data["scope_table"], list):
            for row in data["scope_table"]:
                if "vendors" in row and isinstance(row["vendors"], dict):
                    row["vendors"] = {remap_col(k): val for k, val in row["vendors"].items()}
        if "units" in data and isinstance(data["units"], list):
            for u in data["units"]:
                for p in u.get("parameters", []):
                    if "vendors" in p and isinstance(p["vendors"], dict):
                        p["vendors"] = {remap_col(k): val for k, val in p["vendors"].items()}
                if "discrepancies" in u and isinstance(u["discrepancies"], dict):
                    u["discrepancies"] = {remap_col(k): val for k, val in u["discrepancies"].items()}

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


def extract_document_parameters(doc_text: str, filename: str = "", doc_type_hint: str = "auto", user_preferences: dict = None) -> dict:
    """
    Extracts all relevant HVAC and engineering parameters from a single specification or vendor quotation.
    Summarises and tabulates the data without comparison, grouping parameters by physical equipment units.
    """
    client, model_name, provider = get_ai_client()
    
    clues = extract_document_clues(doc_text, filename)
    email_str = ", ".join(clues["emails"]) if clues["emails"] else "None found"
    domain_str = ", ".join(clues["domains"]) if clues["domains"] else "None"
    ref_str = ", ".join(clues["quote_refs"]) if clues["quote_refs"] else "None"
    proj_str = ", ".join(clues["project_candidates"][:2]) if clues["project_candidates"] else "None explicit"

    hint_instruction = ""
    if doc_type_hint and doc_type_hint.lower() != "auto":
        hint_instruction = f"\nUser Document Nature Hint: Treat this document specifically as a '{doc_type_hint}'."
    
    pref_instructions = build_user_preferences_instructions(user_preferences)

    user_prompt = f"""
You are an independent Principal HVAC Consulting Engineer.

Objective:
Extract all relevant HVAC, mechanical, electrical, and control engineering parameters specified in this single technical document (which may be an Engineering Specification / Equipment Schedule or a Vendor Quotation / Tender Submission).
Normalise engineering units cleanly (e.g. l/s, m³/s, kW, Pa, °C DB/WB, mm, V/Ph/Hz, dB(A), kg).

IMPORTANT:
This is a STANDALONE extraction. Do NOT perform any comparative scoring, compliance pass/fail, or supplier adjudication.
Present all extracted information in an authoritative, structured, summarised, and tabulated format.
{hint_instruction}
{pref_instructions}

Document Clues:
• Source File: {filename}
• Detected Email Domains: {domain_str} ({email_str})
• Detected References: {ref_str}
• Potential Project Names: {proj_str}

Adjudication & Extraction Guidelines:
1. PROJECT & ENTITY IDENTIFICATION:
   - Identify Project Name / Facility / Site (e.g., "Metro Center Central Plant Modernization", "Horizon Medical Center").
   - Identify Document Nature: "Specification" or "Vendor Quotation".
   - Identify Entity Name: Consulting Engineering firm or Vendor / Manufacturer (e.g., "AeroClima", "Carrier", "Trane").
   - Identify Document Reference / Quote Number / Revision.

2. EXECUTIVE TECHNICAL SUMMARY:
   - Provide an objective, comprehensive narrative summary of the document.
   - Use bold markdown headings (e.g., **Document Overview:**, **Salient HVAC Duties:**, **Scope & Demarcation:**).

3. GENERAL SCOPE & DEMARCATION MATRIX:
   - Tabulate general installation, electrical supply, controls / BMS interface, refrigerant type, piping connections, rigging, delivery, warranty, and demarcation items.
   - Each row: "Parameter", "Value", "Notes".

4. MULTI-UNIT EQUIPMENT SCHEDULES:
   - Break down equipment by physical unit / schedule (e.g., "CRAH Units", "AHU-01", "Chiller CH-01").
   - For EACH unit, extract an exhaustive list of all relevant HVAC parameters:
     - Airflows (l/s, m³/s), static pressures (ESP, TSP in Pa).
     - Thermal duties (total cooling, sensible cooling, heating in kW).
     - Coil metrics (air temps °C DB/WB, fluid temps, rows, fin spacing, pressure drops).
     - Fans & motors (EC plug, motor kW, RPM, SFP).
     - Electrical parameters (V, Ph, Hz, FLA, MCA, MOCP).
     - Acoustic data (sound pressure dB(A), sound power LW).
     - Dimensions & weights (L x W x H mm, weight kg).
     - Refrigeration (refrigerant, circuits, compressors).
     - Filtration & casing (pre-filter, final filter, casing thickness, leakage).
     - Controls (integrated controller, BACnet/Modbus card).
   - For each parameter: "Parameter", "Value", "Notes".
   - For EACH unit: "technical_notes" (list of factual engineering notes, features, or observations).

OUTPUT SCHEMA (STRICT JSON ONLY, NO WRAPPER TEXT):
{{
  "project_name": "Identified Project Name",
  "document_type": "Specification" or "Vendor Quotation",
  "document_title": "Identified Document Title / Reference",
  "entity_name": "Identified Company / Engineer / Vendor Name",
  "reference_number": "Reference Number or 'N/A'",
  "executive_summary": "**Document Overview:** ...\\n**Salient HVAC Duties:** ...",
  "scope_table": [
    {{
      "Parameter": "Scope of Supply / Demarcation / Power Supply",
      "Value": "Detailed value / scope description",
      "Notes": "Criteria / Demarcation notes"
    }}
  ],
  "units": [
    {{
      "unit_name": "Equipment Unit Tag & Description",
      "parameters": [
        {{
          "Parameter": "Parameter Name",
          "Value": "Normalized Value with Units",
          "Notes": "Engineering criteria or operating condition"
        }}
      ],
      "technical_notes": [
        "Factual engineering note regarding construction or options."
      ]
    }}
  ]
}}

DOCUMENT TEXT TO EXTRACT:
{doc_text}
"""
    try:
        raw_content = request_text_completion(client, model_name, provider, user_prompt)
    except Exception as e:
        raise Exception(f"API Interface Exception: {str(e)}")

    data = parse_llm_json(raw_content)

    # Fallback / sanitize project name
    proj = data.get("project_name")
    if not proj or str(proj).strip().lower() in ["unknown", "accurately identified project name", "project", "none"]:
        candidate = clues["project_candidates"][0] if clues.get("project_candidates") else ""
        data["project_name"] = candidate or (clean_company_name(filename) if filename else "HVAC Engineering Project")
    else:
        data["project_name"] = str(proj).strip()

    # Fallback for entity name
    if not data.get("entity_name") or str(data.get("entity_name")).strip().lower() in ["unknown", "none", "entity"]:
        if clues.get("domains"):
            data["entity_name"] = clean_company_name(clues["domains"][0])
        elif filename:
            data["entity_name"] = clean_company_name(filename)
        else:
            data["entity_name"] = "Engineering Document"
    else:
        data["entity_name"] = clean_company_name(data["entity_name"])

    return data



