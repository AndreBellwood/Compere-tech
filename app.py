import streamlit as st
import os
import time
import pandas as pd
from services.document_service import extract_document_text, extract_multiple_documents, clean_company_name
from services.ai_service import compare_spec_with_offers
from services.report_service import generate_pdf_report

st.set_page_config(layout="wide", page_title="COMPèRE - HVAC Technical Compliance Terminal")

# Professional Corporate Styling: Larger bold buttons, darker outline, dotted file upload zones
st.markdown("""
<style>
/* 1. All Clickable Buttons: 15% larger, bold, darker outline, darker text */
.stButton > button,
.stDownloadButton > button,
div[data-testid="stFileUploader"] section button {
    font-size: 16px !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    border: 2px solid #334155 !important;
    border-radius: 6px !important;
    padding: 0.65rem 1.4rem !important;
    background-color: #FFFFFF !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
    transition: all 0.15s ease-in-out !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
div[data-testid="stFileUploader"] section button:hover {
    color: #000000 !important;
    border-color: #0F172A !important;
    background-color: #F1F5F9 !important;
    box-shadow: 0 3px 6px rgba(0, 0, 0, 0.1) !important;
}

.stButton > button:active,
.stDownloadButton > button:active {
    background-color: #E2E8F0 !important;
    border-color: #000000 !important;
}

.stButton > button:disabled,
.stDownloadButton > button:disabled {
    color: #64748B !important;
    border-color: #CBD5E1 !important;
    background-color: #F8FAFC !important;
    cursor: not-allowed !important;
}

/* 2. File Upload Areas: Dotted outline & light grey background */
[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploadDropzone"],
div[data-testid="stFileUploader"] section,
div[data-testid="stFileUploader"] > div > section {
    border: 2px dotted #94A3B8 !important;
    background-color: #F8FAFC !important;
    border-radius: 8px !important;
    padding: 1.5rem !important;
}

[data-testid="stFileUploaderDropzone"]:hover,
[data-testid="stFileUploadDropzone"]:hover,
div[data-testid="stFileUploader"] section:hover,
div[data-testid="stFileUploader"] > div > section:hover {
    border: 2px dotted #475569 !important;
    background-color: #F1F5F9 !important;
}
</style>
""", unsafe_allow_html=True)

st.title("COMPèRE - HVAC Technical Compliance Terminal")

st.info("Multi-Vendor Audit Portal: Upload the Consulting Engineer's Specification (single or multiple documents across PDF, Excel, Word, or text) alongside one or more Vendor Quotations / Offers for automated comparative compliance adjudication.")

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

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("### 1. Specification")
    spec_uploads = st.file_uploader(
        "Upload Specifications (Add 1 or more: PDF, Word, Excel, TXT)",
        type=["pdf", "docx", "xlsx", "xls", "txt", "csv", "rtf", "md"],
        accept_multiple_files=True,
        key="spec_uploader"
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
    offer_uploads = st.file_uploader(
        "Upload Vendor Offers (Add one or several at a time)",
        type=["pdf", "docx", "xlsx", "xls", "txt", "csv", "rtf", "md"],
        accept_multiple_files=True,
        key="offer_uploader"
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
    logo_file = st.file_uploader("Specifier Logo / Header (Optional)", type=["png", "jpg", "jpeg"], key="logo_uploader")

ready_to_audit = len(st.session_state["staged_specs"]) > 0 and len(st.session_state["staged_offers"]) > 0

# Side-by-side action buttons: Execute on left, Download Report on right when ready
col_exec, col_dl = st.columns([1, 1])

with col_exec:
    btn_execute = st.button("Execute Technical Compliance Audit", disabled=not ready_to_audit, key="btn_exec_audit")

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
    
    results = compare_spec_with_offers(spec_text, vendor_offers)
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
