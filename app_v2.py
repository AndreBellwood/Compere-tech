import streamlit as st
import os
import time
import importlib
import pandas as pd
import services.document_service
import services.ai_service
import services.report_service
import services.extraction_view

# Always reload service modules so edits take effect immediately without module caching
importlib.reload(services.document_service)
importlib.reload(services.ai_service)
importlib.reload(services.report_service)
importlib.reload(services.extraction_view)

from services.document_service import extract_document_text, extract_multiple_documents, clean_company_name
from services.ai_service import compare_spec_with_offers
from services.report_service import generate_pdf_report
from services.extraction_view import render_standalone_extraction

st.set_page_config(layout="wide", page_title="COMPèRE - HVAC Technical Compliance Terminal (Corporate Dark)")

with open("theme_v2.css", "r", encoding="utf-8") as f:
    custom_dark_css = f.read()

st.markdown(f"<style>{custom_dark_css}</style>", unsafe_allow_html=True)

# ─── A/B TESTING NAVIGATION BANNER ───
st.markdown("""
<aside style="
    background: linear-gradient(90deg, #0F172A 0%, #1A365D 50%, #0F172A 100%);
    border: 1px solid #1E293B;
    border-radius: 8px;
    padding: 0.6rem 1rem;
    margin-bottom: 1.25rem;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.4);
">
    <div style="display: flex; align-items: center; gap: 8px;">
        <span style="
            background-color: rgba(56, 189, 248, 0.2);
            color: #38BDF8;
            border: 1px solid rgba(56, 189, 248, 0.4);
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 800;
            padding: 2px 10px;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        ">A/B Testing: Version B</span>
        <span style="font-size: 13.5px; font-weight: 600; color: #FFFFFF;">
            Corporate Dark Overview Theme (Active: Port 8502)
        </span>
    </div>
    <div style="display: flex; align-items: center; gap: 10px;">
        <a href="http://localhost:8501" target="_blank" style="
            text-decoration: none;
            font-size: 12.5px;
            font-weight: 700;
            color: #CBD5E1;
            background-color: #1E293B;
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 0.4rem 0.8rem;
            transition: all 0.15s;
        ">
            Switch to Version A (Port 8501) &rarr;
        </a>
        <a href="http://localhost:8080" target="_blank" style="
            text-decoration: none;
            font-size: 12.5px;
            font-weight: 700;
            color: #38BDF8;
            background-color: rgba(56, 189, 248, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 6px;
            padding: 0.4rem 0.8rem;
        ">
            🌐 Corporate Overview Docs &rarr;
        </a>
    </div>
</aside>
""", unsafe_allow_html=True)

col_title, col_site_link = st.columns([3, 1])
with col_title:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 0.5rem;">
        <div style="
            width: 44px;
            height: 44px;
            border-radius: 10px;
            background: linear-gradient(135deg, #0284C7 0%, #0F172A 100%);
            border: 1.5px solid #38BDF8;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(56, 189, 248, 0.3);
            font-weight: 800;
            color: #FFFFFF;
            font-size: 20px;
        ">C</div>
        <div>
            <h1 style="font-size: 28px; font-weight: 800; margin: 0; line-height: 1.2; color: #FFFFFF;">
                COMP<span style="color: #38BDF8;">è</span>RE 
                <span style="font-size: 11px; font-weight: 700; color: #38BDF8; background: rgba(56,189,248,0.15); border: 1px solid rgba(56,189,248,0.3); padding: 3px 8px; border-radius: 4px; text-transform: uppercase; vertical-align: middle; margin-left: 6px;">HVAC Terminal</span>
            </h1>
            <p style="font-size: 13px; color: #94A3B8; margin: 0;">Multi-Vendor Compliance Adjudication & Technical Parameter Schedule Engine</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
with col_site_link:
    st.markdown("""
    <div style="text-align: right; padding-top: 0.75rem;">
        <a href="http://localhost:8080" target="_blank" style="
            text-decoration: none;
            font-size: 13px;
            font-weight: 700;
            color: #38BDF8;
            background-color: #0F172A;
            border: 1px solid #1E293B;
            border-radius: 8px;
            padding: 0.55rem 1rem;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        ">
            🌐 Corporate Overview & Docs
        </a>
    </div>
    """, unsafe_allow_html=True)


# Initialize persistent session state for cumulative file staging & results
if "staged_specs" not in st.session_state:
    st.session_state["staged_specs"] = {}
if "staged_offers" not in st.session_state:
    st.session_state["staged_offers"] = {}
if "audit_results" not in st.session_state:
    st.session_state["audit_results"] = None
if "report_pdf_bytes" not in st.session_state:
    st.session_state["report_pdf_bytes"] = None
if "report_pdf_filename" not in st.session_state:
    st.session_state["report_pdf_filename"] = "Compliance_Report.pdf"
if "app_mode" not in st.session_state:
    st.session_state["app_mode"] = "audit"

# Top Control Row: Operating Mode (left) and User Preferences (right) side-by-side
col_mode_box, col_prefs_box = st.columns([1, 2.5])

with col_mode_box:
    with st.container(border=True):
        st.markdown("<span id='mode-section-marker'></span>", unsafe_allow_html=True)
        st.markdown("### Operating Mode")
        is_audit = st.session_state["app_mode"] == "audit"
        
        audit_lbl = "● Multi-Vendor Compliance Audit  (Active)" if is_audit else "Multi-Vendor Compliance Audit"
        extract_lbl = "● Standalone Parameter Extraction  (Active)" if not is_audit else "Standalone Parameter Extraction"

        if st.button(
            audit_lbl,
            key="btn_mode_audit",
            use_container_width=True,
            help="Multi-Vendor Audit Portal: Upload the Consulting Engineer's Specification alongside one or more Vendor Quotations / Offers for automated comparative compliance adjudication."
        ):
            st.session_state["app_mode"] = "audit"
            st.rerun()

        if st.button(
            extract_lbl,
            key="btn_mode_extract",
            use_container_width=True,
            help="Standalone Parameter Extraction: Upload an Engineering Specification or Vendor Quotation to extract, normalize, and tabulate HVAC parameters into a clean schedule without comparison."
        ):
            st.session_state["app_mode"] = "extraction"
            st.rerun()

with col_prefs_box:
    with st.container(border=True):
        st.markdown("<span id='pref-section-marker'></span>", unsafe_allow_html=True)
        st.markdown("### User Preferences")
        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            with st.container(border=True):
                st.markdown("<span id='pref-subcard-marker'></span>", unsafe_allow_html=True)
                scope_choice = st.selectbox(
                    "Equipment Scope",
                    options=[
                        "Auto-select (All Equipment)",
                        "CHW Units, DX AHUs, Roof-top packages and hybrid units larger than 10kW capacity",
                        "Splits, ducted splits, cassettes smaller than 10kW"
                    ],
                    index=0,
                    key="user_pref_scope",
                    help="Limit extraction or comparative audit to your designated equipment field or capacity tier."
                )
        with p_col2:
            with st.container(border=True):
                st.markdown("<span id='pref-subcard-marker'></span>", unsafe_allow_html=True)
                curr_choice = st.selectbox(
                    "Preferred Trading Currency",
                    options=[
                        "Document Default (Currency used by Specification)",
                        "ZAR - South African Rand (R)",
                        "USD - US Dollar ($)",
                        "EUR - Euro (€)",
                        "GBP - British Pound (£)",
                        "AED - UAE Dirham (AED)",
                        "AUD - Australian Dollar (A$)",
                        "CAD - Canadian Dollar (C$)"
                    ],
                    index=0,
                    key="user_pref_currency",
                    help="All prices, rates, and costs for this session are converted at the daily spot rate and displayed in this currency."
                )
        with p_col3:
            with st.container(border=True):
                st.markdown("<span id='pref-subcard-marker'></span>", unsafe_allow_html=True)
                units_choice = st.selectbox(
                    "Preferred Measurement Units",
                    options=[
                        "Document Default (Units used by Specification)",
                        "Metric (SI: kW, l/s, m³/s, Pa, °C DB/WB, mm, kg)",
                        "Imperial (US: Tons/BTU/h, CFM, in.wg, °F DB/WB, in, lbs)",
                        "Asian (Regional: kcal/h, RT, m³/h, mmAq, °C)",
                        "Mixed (Dual Units: e.g. kW / TR, l/s / CFM, °C / °F)"
                    ],
                    index=0,
                    key="user_pref_units",
                    help="Select preferred engineering unit system for all parameter schedules and tables."
                )

st.session_state["user_preferences"] = {
    "equipment_scope": scope_choice,
    "preferred_currency": curr_choice.split(" - ")[0] if " - " in curr_choice else "Document Default",
    "preferred_units": units_choice.split(" (")[0] if " (" in units_choice else units_choice
}

if st.session_state["app_mode"] == "extraction":
    render_standalone_extraction()
    st.stop()

# 3. Document Upload Section (Clearly demarcated, uniform #d3d8e3 background)
with st.container(border=True):
    st.markdown("<span id='upload-section-marker'></span>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 1. Specification")
        st.caption("Upload from a folder or simply drag & drop files here.")
        spec_uploads = st.file_uploader(
            "Specification Documents (PDF, Word, Excel, TXT)",
            type=["pdf", "docx", "xlsx", "xls", "txt", "csv", "rtf", "md"],
            accept_multiple_files=True,
            key="spec_uploader",
            help="Upload from a folder by clicking 'Browse files', or simply drag & drop files directly into this upload area."
        )
        if spec_uploads:
            for sf in spec_uploads:
                st.session_state["staged_specs"][sf.name] = sf.getvalue()
        
        if st.session_state["staged_specs"]:
            st.success(f"**{len(st.session_state['staged_specs'])} Specification File(s) Staged:**")
            for s_name in list(st.session_state["staged_specs"].keys()):
                st.caption(f"• {s_name}")
            if st.button("Clear Specifications", key="btn_clear_specs"):
                st.session_state["staged_specs"] = {}
                st.rerun()

    with col2:
        st.markdown("### 2. Vendor Offers")
        st.caption("Upload from a folder or simply drag & drop files here.")
        offer_uploads = st.file_uploader(
            "Vendor Quotations / Offers (PDF, Word, Excel, TXT)",
            type=["pdf", "docx", "xlsx", "xls", "txt", "csv", "rtf", "md"],
            accept_multiple_files=True,
            key="offer_uploader",
            help="Upload from a folder by clicking 'Browse files', or simply drag & drop files directly into this upload area."
        )
        if offer_uploads:
            for of in offer_uploads:
                st.session_state["staged_offers"][of.name] = of.getvalue()
                
        if st.session_state["staged_offers"]:
            st.success(f"**{len(st.session_state['staged_offers'])} Vendor Offer(s) Staged:**")
            for o_name in list(st.session_state["staged_offers"].keys()):
                st.caption(f"• {o_name}")
            if st.button("Clear Offers", key="btn_clear_offers"):
                st.session_state["staged_offers"] = {}
                st.rerun()

    with col3:
        st.markdown("### 3. Corporate Branding")
        st.caption("Upload from a folder or simply drag & drop files here.")
        logo_file = st.file_uploader(
            "Corporate Header / Logo (Optional Image)",
            type=["png", "jpg", "jpeg"],
            key="logo_uploader",
            help="Upload from a folder by clicking 'Browse files', or simply drag & drop your corporate header or logo image here."
        )

ready_to_audit = len(st.session_state["staged_specs"]) > 0 and len(st.session_state["staged_offers"]) > 0

# Side-by-side action buttons: Execute on left, Download Report on right when ready
col_exec, col_dl = st.columns([1, 1])

with col_exec:
    btn_execute = st.button("Execute Technical Compliance Audit", disabled=not ready_to_audit, key="btn_exec_audit", type="primary")

with col_dl:
    dl_placeholder = st.empty()
    if st.session_state.get("report_pdf_bytes"):
        dl_placeholder.download_button(
            label="Download Corporate PDF Report",
            data=st.session_state["report_pdf_bytes"],
            file_name=st.session_state.get("report_pdf_filename", "Compliance_Report.pdf"),
            mime="application/pdf",
            key="btn_download_top"
        )

if btn_execute:
    os.makedirs("uploads/specs", exist_ok=True)
    os.makedirs("uploads/offers", exist_ok=True)
    
    status_box = st.empty()
    p1 = st.progress(0)

    # 1. Save and extract specifications
    with status_box.container():
        st.write("*Consolidating specification files across formats...*")
    time.sleep(0.3)
    p1.progress(15)

    spec_paths = []
    for s_name, s_bytes in st.session_state["staged_specs"].items():
        s_path = os.path.join("uploads", "specs", s_name)
        with open(s_path, "wb") as f:
            f.write(s_bytes)
        spec_paths.append(s_path)

    if len(spec_paths) == 1:
        spec_text = extract_document_text(spec_paths[0])
    else:
        spec_text = extract_multiple_documents(spec_paths)

    # 2. Save and extract vendor offers
    vendor_offers = []
    total_offers = len(st.session_state["staged_offers"])
    for idx, (o_name, o_bytes) in enumerate(st.session_state["staged_offers"].items()):
        o_path = os.path.join("uploads", "offers", o_name)
        with open(o_path, "wb") as f:
            f.write(o_bytes)
        with status_box.container():
            st.write(f"*Extracting vendor offer ({idx+1}/{total_offers}): {o_name}...*")
        v_text = extract_document_text(o_path)
        vendor_offers.append({"filename": o_name, "vendor_name": o_name, "text": v_text})
        p1.progress(15 + int(35 * (idx + 1) / total_offers))

    logo_path = None
    if logo_file:
        logo_path = os.path.join("uploads", logo_file.name)
        with open(logo_path, "wb") as f:
            f.write(logo_file.getvalue())

    # 3. AI Compliance Cross-Examination
    with status_box.container():
        st.write("*Running multi-vendor cross-examination & unit normalization matrix...*")
    
    user_prefs = st.session_state.get("user_preferences", {})
    results = compare_spec_with_offers(spec_text, vendor_offers, user_preferences=user_prefs)
    p1.progress(85)

    # 4. Generate Corporate PDF Ledger
    with status_box.container():
        st.write("*Generating corporate compliance ledger and dynamic pagination...*")
    report_out = os.path.join("uploads", "Compliance_Report.pdf")
    generate_pdf_report(report_out, results, logo_path)
    
    with open(report_out, "rb") as f:
        pdf_bytes = f.read()

    project_name = results.get("project_name", "HVAC Engineering Project")
    pdf_filename = f"{clean_company_name(project_name)}_Compliance_Report.pdf"

    # Persist in session state
    st.session_state["audit_results"] = results
    st.session_state["report_pdf_bytes"] = pdf_bytes
    st.session_state["report_pdf_filename"] = pdf_filename

    # Populate download button next to Execute button
    dl_placeholder.download_button(
        label="Download Corporate PDF Report",
        data=pdf_bytes,
        file_name=pdf_filename,
        mime="application/pdf",
        key="btn_download_immediate"
    )

    p1.progress(100)
    status_box.empty()
    st.success("Adjudication Complete.")

# ─── DISPLAY RESULTS: PROFESSIONAL & OBJECTIVE ───
results_to_display = st.session_state.get("audit_results")

if results_to_display:
    project_name = results_to_display.get("project_name", "HVAC Engineering Project")
    st.divider()
    st.header("Technical Compliance Audit Review")
    st.info(f"**Identified Project:** {project_name}")

    st.subheader("Executive Review Summary")
    exec_summary_text = results_to_display.get("executive_summary", "No executive summary provided.")
    st.markdown(exec_summary_text)

    # Vendor Compliance Leaderboard
    v_scores = results_to_display.get("vendor_scores", [])
    if v_scores:
        st.subheader("Vendor Compliance Adjudication Leaderboard")
        cols = st.columns(min(len(v_scores), 4))
        clean_scores = []
        for idx, score_info in enumerate(v_scores):
            c_name = clean_company_name(score_info.get("vendor_name", "Vendor"))
            col_target = cols[idx % len(cols)]
            with col_target:
                pct = score_info.get("compliance_percent", 0.0)
                st.metric(
                    label=c_name,
                    value=f"{pct}%",
                    delta=f"{score_info.get('passed_count', 0)} Pass | {score_info.get('marginal_count', 0)} TBC | {score_info.get('failed_count', 0)} Fail"
                )
            clean_scores.append({
                "Vendor Offer / Submission": c_name,
                "Compliance %": f"{pct}%",
                "Passed": score_info.get("passed_count", 0),
                "Marginal / TBC": score_info.get("marginal_count", 0),
                "Failed": score_info.get("failed_count", 0)
            })
        st.dataframe(pd.DataFrame(clean_scores), use_container_width=True)

    # Overarching Scope Table
    scope_rows = results_to_display.get("scope_table", [])
    if scope_rows:
        st.subheader("General Scope & Demarcation Matrix")
        flat_scope = []
        for r in scope_rows:
            row_dict = {
                "Parameter": r.get("Parameter", ""),
                "Specification Requirement": r.get("Spec_Requirement", "")
            }
            if "vendors" in r:
                for vn, vd in r["vendors"].items():
                    clean_vn = clean_company_name(vn)
                    row_dict[f"{clean_vn}"] = f"{vd.get('value', '—')} [{vd.get('status', '')}]"
            elif "Offer_Value" in r:
                row_dict["Supplier Offer"] = r.get("Offer_Value", "")
                row_dict["Status"] = r.get("Status", "")
            flat_scope.append(row_dict)
        st.dataframe(pd.DataFrame(flat_scope), use_container_width=True)

    # Multi-Unit Evaluations
    units = results_to_display.get("units", [])
    if units:
        for unit in units:
            st.divider()
            st.subheader(unit.get('unit_name', 'Equipment Unit'))
            unit_params = unit.get("parameters", [])
            if unit_params:
                flat_params = []
                for p in unit_params:
                    row_dict = {
                        "Parameter": p.get("Parameter", ""),
                        "Specification Requirement": p.get("Spec_Requirement", "")
                    }
                    if "vendors" in p:
                        for vn, vd in p["vendors"].items():
                            clean_vn = clean_company_name(vn)
                            row_dict[f"{clean_vn}"] = f"{vd.get('value', '—')} [{vd.get('status', '')}]"
                    elif "Offer_Value" in p:
                        row_dict["Supplier Offer"] = p.get("Offer_Value", "")
                        row_dict["Status"] = p.get("Status", "")
                    flat_params.append(row_dict)
                st.dataframe(pd.DataFrame(flat_params), use_container_width=True)

            unit_disc = unit.get("discrepancies", {})
            if unit_disc:
                st.markdown("**Technical Notes & Specific Discrepancies:**")
                if isinstance(unit_disc, dict):
                    for raw_vn, notes in unit_disc.items():
                        c_vn = clean_company_name(raw_vn)
                        st.markdown(f"**{c_vn}:**")
                        for note in notes:
                            st.markdown(f"* {note}")
                elif isinstance(unit_disc, list):
                    for note in unit_disc:
                        st.markdown(f"* {note}")
