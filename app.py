import streamlit as st
import os
import time
import importlib
import pandas as pd
import config
import services.document_service
import services.ai_service
import services.report_service
import services.extraction_view

# Always reload service modules and config so edits take effect immediately
importlib.reload(config)
importlib.reload(services.document_service)
importlib.reload(services.ai_service)
importlib.reload(services.report_service)
importlib.reload(services.extraction_view)

from services.document_service import extract_document_text, extract_multiple_documents, clean_company_name
from services.ai_service import compare_spec_with_offers
from services.report_service import generate_pdf_report
from services.extraction_view import render_standalone_extraction

st.set_page_config(layout="wide", page_title="COMPèRE - HVAC Technical Compliance Terminal")

# Professional Corporate Styling: High contrast, dark demarcated tiers, prominent actions
st.markdown("""
<style>
/* 1. All Standard Clickable Buttons: Bold, clean outline */
.stButton > button,
div[data-testid="stFileUploader"] section button {
    font-size: 15px !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    border: 1.5px solid #64748B !important;
    border-radius: 6px !important;
    padding: 0.6rem 1.3rem !important;
    background-color: #FFFFFF !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
    transition: all 0.15s ease-in-out !important;
}

.stButton > button:hover,
div[data-testid="stFileUploader"] section button:hover {
    color: #000000 !important;
    border-color: #0F172A !important;
    background-color: #F8FAFC !important;
    box-shadow: 0 3px 6px rgba(0, 0, 0, 0.12) !important;
}

/* 2. High Emphasis Primary Action Buttons (Execute Audit / Extract Parameters) */
button[kind="primary"],
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background-color: #1A365D !important;
    border: 2.5px solid #0F172A !important;
    border-radius: 6px !important;
    font-size: 17px !important;
    font-weight: 800 !important;
    letter-spacing: 0.02em !important;
    box-shadow: 0 4px 14px rgba(26, 54, 93, 0.4) !important;
    padding: 0.75rem 1.6rem !important;
    -webkit-font-smoothing: antialiased !important;
}

button[kind="primary"] *,
.stButton > button[kind="primary"] *,
button[data-testid="baseButton-primary"] * {
    color: #FFFFFF !important;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5) !important;
}

button[kind="primary"]:hover,
.stButton > button[kind="primary"]:hover,
button[data-testid="baseButton-primary"]:hover {
    background-color: #2A4365 !important;
    border-color: #000000 !important;
    box-shadow: 0 6px 18px rgba(26, 54, 93, 0.5) !important;
    transform: translateY(-1px) !important;
}

button[kind="primary"]:hover *,
.stButton > button[kind="primary"]:hover *,
button[data-testid="baseButton-primary"]:hover * {
    color: #FFFFFF !important;
}

button[kind="primary"]:disabled,
.stButton > button[kind="primary"]:disabled {
    background-color: #94A3B8 !important;
    border-color: #CBD5E1 !important;
    box-shadow: none !important;
    cursor: not-allowed !important;
}

button[kind="primary"]:disabled * {
    color: #F1F5F9 !important;
}

/* 3. High Emphasis Download Report Buttons (Emerald Corporate Success) */
.stDownloadButton > button,
div[data-testid="stDownloadButton"] button {
    background-color: #047857 !important;
    color: #FFFFFF !important;
    border: 2.5px solid #064E3B !important;
    border-radius: 6px !important;
    font-size: 17px !important;
    font-weight: 800 !important;
    letter-spacing: 0.02em !important;
    box-shadow: 0 4px 14px rgba(4, 120, 87, 0.35) !important;
    padding: 0.75rem 1.6rem !important;
}

.stDownloadButton > button:hover,
div[data-testid="stDownloadButton"] button:hover {
    background-color: #059669 !important;
    color: #FFFFFF !important;
    border-color: #064E3B !important;
    box-shadow: 0 6px 18px rgba(4, 120, 87, 0.5) !important;
    transform: translateY(-1px) !important;
}

/* 4. Mouse-Over Tooltips: Responsive, Disappears on Mouse-Leave, Never Sticks */
div[data-baseweb="tooltip"],
div[role="tooltip"] {
    pointer-events: none !important;
}

div[data-testid="stTooltipContent"] {
    background-color: #1c212e !important;
    color: #F8FAFC !important;
    border: 2px solid #38BDF8 !important;
    border-radius: 8px !important;
    padding: 12px 16px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    line-height: 1.5 !important;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.6) !important;
    max-width: 440px !important;
    pointer-events: none !important;
    transition: opacity 0.12s ease-out !important;
}

div[data-testid="stTooltipContent"] * {
    color: #F8FAFC !important;
    font-size: 14px !important;
}

/* 5. Dropdown Menus: Clearly outlined when dropped & highly legible text */
div[data-baseweb="popover"],
ul[role="listbox"],
div[data-baseweb="menu"] {
    border: 2.5px solid #1E293B !important;
    border-radius: 8px !important;
    background-color: #FFFFFF !important;
    box-shadow: 0 12px 30px rgba(15, 23, 42, 0.28) !important;
}

li[role="option"] {
    font-size: 15px !important;
    font-weight: 500 !important;
    color: #0F172A !important;
    padding: 10px 14px !important;
    border-bottom: 1px solid #F1F5F9 !important;
}

li[role="option"]:hover,
li[role="option"][aria-selected="true"] {
    background-color: #E2E8F0 !important;
    color: #000000 !important;
    font-weight: 700 !important;
}

div[data-baseweb="select"] > div {
    border: 2px solid #64748b !important;
    border-radius: 6px !important;
    font-size: 14.5px !important;
    background-color: #bac2d0 !important;
}

/* 6. Section Demarcation Containers: Uniform shading #dfe2eb across all containers */
div[data-testid="stVerticalBlockBorderWrapper"]:has(#mode-section-marker),
div[data-testid="stVerticalBlockBorderWrapper"]:has(#mode-section-marker) > div,
div[data-testid="stVerticalBlockBorderWrapper"]:has(#pref-section-marker),
div[data-testid="stVerticalBlockBorderWrapper"]:has(#pref-section-marker) > div,
div[data-testid="stVerticalBlockBorderWrapper"]:has(#upload-section-marker),
div[data-testid="stVerticalBlockBorderWrapper"]:has(#upload-section-marker) > div {
    background-color: #dfe2eb !important;
    border: 1.5px solid #8e9db3 !important;
    border-radius: 8px !important;
    padding: 1rem 1.25rem !important;
}

/* Outlined option cards inside User Preferences */
div[data-testid="stVerticalBlockBorderWrapper"]:has(#pref-subcard-marker),
div[data-testid="stVerticalBlockBorderWrapper"]:has(#pref-subcard-marker) > div {
    background-color: #dfe2eb !important;
    border: 1.5px solid #8e9db3 !important;
    border-radius: 6px !important;
    padding: 0.6rem 0.85rem !important;
}

/* Ensure equal baseline alignment for file upload header labels */
div[data-testid="stVerticalBlockBorderWrapper"]:has(#upload-section-marker) div[data-testid="stFileUploader"] label[data-testid="stWidgetLabel"],
div[data-testid="stVerticalBlockBorderWrapper"]:has(#upload-section-marker) div[data-testid="stSelectbox"] label[data-testid="stWidgetLabel"] {
    min-height: 2.4rem !important;
    display: flex !important;
    align-items: flex-end !important;
    margin-bottom: 0.25rem !important;
}

/* Emphasised dropdown block headings under User Preferences: 16pt and bold */
div[data-testid="stVerticalBlockBorderWrapper"]:has(#pref-section-marker) label[data-testid="stWidgetLabel"] p,
div[data-testid="stVerticalBlockBorderWrapper"]:has(#pref-section-marker) label[data-testid="stWidgetLabel"] span {
    font-size: 16pt !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    line-height: 1.3 !important;
}

/* Ensure headings inside Operating Mode and User Preferences align with Specification headings */
div[data-testid="stVerticalBlockBorderWrapper"]:has(#mode-section-marker) h3,
div[data-testid="stVerticalBlockBorderWrapper"]:has(#pref-section-marker) h3 {
    margin-top: 0 !important;
    margin-bottom: 0.5rem !important;
    color: #0F172A !important;
    font-weight: 700 !important;
}

/* 7. File Upload Dropzones: Darker shading inside container */
[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploadDropzone"],
div[data-testid="stFileUploader"] section,
div[data-testid="stFileUploader"] > div > section {
    border: 2px dotted #475569 !important;
    background-color: #bac2d0 !important;
    border-radius: 8px !important;
    padding: 1.5rem !important;
}

[data-testid="stFileUploaderDropzone"]:hover,
[data-testid="stFileUploadDropzone"]:hover,
div[data-testid="stFileUploader"] section:hover,
div[data-testid="stFileUploader"] > div > section:hover {
    border: 3px dotted #1E293B !important;
    background-color: #a4b0c2 !important;
}
</style>

<script>
// Prevent buttons from retaining persistent focus upon click so tooltips dismiss immediately
document.addEventListener('mouseup', function(e) {
    if (e.target && (e.target.tagName === 'BUTTON' || e.target.closest('button'))) {
        const btn = e.target.tagName === 'BUTTON' ? e.target : e.target.closest('button');
        setTimeout(() => btn.blur(), 80);
    }
});

// Enforce single active tooltip and clean mouse-leave dismissals
let lastActiveTooltip = null;
document.addEventListener('mouseover', function(e) {
    const tt = document.querySelector('div[data-testid="stTooltipContent"], div[role="tooltip"]');
    if (tt && tt !== lastActiveTooltip) {
        // Dismiss previous stray tooltips
        const allTooltips = document.querySelectorAll('div[data-testid="stTooltipContent"], div[role="tooltip"]');
        allTooltips.forEach(item => {
            if (item !== tt && item.parentElement) {
                item.parentElement.style.display = 'none';
            }
        });
        lastActiveTooltip = tt;
    }
}, true);

document.addEventListener('scroll', function() {
    const allTooltips = document.querySelectorAll('div[data-testid="stTooltipContent"], div[role="tooltip"]');
    allTooltips.forEach(item => {
        if (item.parentElement) item.parentElement.style.display = 'none';
    });
}, true);
</script>
""", unsafe_allow_html=True)

# ─── OPTIONAL BETA ACCESS PASSKEY GATE ───
beta_access_code = getattr(config, "BETA_ACCESS_CODE", "").strip()
if beta_access_code:
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        col_c1, col_c2, col_c3 = st.columns([1, 1.6, 1])
        with col_c2:
            st.markdown("""
            <div style="background: #FFFFFF; border: 2px solid #1A365D; border-radius: 12px; padding: 2rem; box-shadow: 0 10px 25px rgba(15, 23, 42, 0.12); text-align: center; margin-top: 3rem; margin-bottom: 1.5rem;">
                <div style="width: 52px; height: 52px; line-height: 52px; background: #1A365D; color: #FFFFFF; border-radius: 10px; font-size: 24px; margin: 0 auto 1rem auto;">
                    🔒
                </div>
                <h2 style="color: #0F172A; font-size: 22px; font-weight: 800; margin: 0 0 6px 0;">COMPèRE Beta Evaluation</h2>
                <p style="color: #475569; font-size: 13.5px; line-height: 1.5; margin: 0 0 1.25rem 0;">
                    Terminal access is currently restricted to authorized consulting engineering beta partners. Please enter your evaluation passkey.
                </p>
            </div>
            """, unsafe_allow_html=True)
            with st.form("beta_auth_form"):
                passkey = st.text_input("Enter Beta Passkey", type="password", placeholder="e.g. COMPERE-BETA-2026")
                submitted = st.form_submit_button("Unlock Terminal", type="primary", use_container_width=True)
                if submitted:
                    if passkey.strip() == beta_access_code:
                        st.session_state["authenticated"] = True
                        st.rerun()
                    else:
                        st.error("Invalid Beta Passkey. Please verify with your project lead.")
            st.markdown("""
            <div style="text-align: center; margin-top: 1rem;">
                <a href="https://compere.tech" target="_blank" style="color: #64748B; font-size: 12px; text-decoration: underline;">
                    View COMPèRE Documentation & Overview &rarr;
                </a>
            </div>
            """, unsafe_allow_html=True)
        st.stop()

col_title, col_site_link = st.columns([3, 1])
with col_title:
    st.title("COMPèRE - HVAC Technical Compliance Terminal")
with col_site_link:
    st.markdown("""
    <div style="text-align: right; padding-top: 1.2rem;">
        <a href="https://compere.tech" target="_blank" style="
            text-decoration: none;
            font-size: 13.5px;
            font-weight: 700;
            color: #1A365D;
            background-color: #dfe2eb;
            border: 1.5px solid #8e9db3;
            border-radius: 6px;
            padding: 0.5rem 0.9rem;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
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
                st.markdown("**Equipment Scope**")
                
                EQUIPMENT_SCOPE_ITEMS = [
                    "Chilled Water/Hot Water Air Handlers.",
                    "FCU Fan Coil Units.",
                    "Roof-top Packages.",
                    "Stand-alone DX Evap Units (excl condensers).",
                    "Hybrid Roof-top packages.",
                    "Split Units and ducted splits <10kW",
                    "Cassettes. <10kW"
                ]
                
                chk_all = st.checkbox("Select All Equipment Categories", value=True, key="chk_scope_all")
                selected_scopes = []
                for item in EQUIPMENT_SCOPE_ITEMS:
                    val = st.checkbox(item, value=chk_all, key=f"chk_{item}")
                    if val:
                        selected_scopes.append(item)
                
                scope_choice = selected_scopes if len(selected_scopes) > 0 else EQUIPMENT_SCOPE_ITEMS

        with p_col2:
            with st.container(border=True):
                st.markdown("<span id='pref-subcard-marker'></span>", unsafe_allow_html=True)
                curr_choice = st.selectbox(
                    "Preferred Trading Currency",
                    options=[
                        "Document Default (Currency used by Specification)",
                        "AED - UAE Dirham (AED)",
                        "AUD - Australian Dollar (A$)",
                        "CAD - Canadian Dollar (C$)",
                        "CNY - Chinese Yuan (¥)",
                        "EUR - Euro (€)",
                        "GBP - British Pound (£)",
                        "JPY - Japanese Yen (¥)",
                        "USD - US Dollar ($)",
                        "ZAR - Rand (R)"
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
            "Specification Documents (PDF, Word, Excel, TXT, Images)",
            type=["pdf", "docx", "xlsx", "xls", "txt", "csv", "rtf", "md", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"],
            accept_multiple_files=True,
            key="spec_uploader",
            help="Upload from a folder by clicking 'Browse files', or simply drag & drop files directly into this upload area."
        )
        if spec_uploads:
            for sf in spec_uploads:
                st.session_state["staged_specs"][sf.name] = sf.getvalue()
        
        specifier_firm = st.text_input(
            "Specifier's Company Name (Optional)",
            value=st.session_state.get("specifier_company", ""),
            key="specifier_company_input",
            placeholder="e.g. CRC Consulting Engineers",
            help="Type in the consulting engineering practice or specifier firm name."
        )
        st.session_state["specifier_company"] = specifier_firm

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
            "Vendor Quotations / Offers (PDF, Word, Excel, TXT, Images)",
            type=["pdf", "docx", "xlsx", "xls", "txt", "csv", "rtf", "md", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"],
            accept_multiple_files=True,
            key="offer_uploader",
            help="Upload from a folder by clicking 'Browse files', or simply drag & drop files directly into this upload area."
        )
        if offer_uploads:
            for of in offer_uploads:
                st.session_state["staged_offers"][of.name] = of.getvalue()

        if "vendor_name_overrides" not in st.session_state:
            st.session_state["vendor_name_overrides"] = {}
                
        if st.session_state["staged_offers"]:
            st.success(f"**{len(st.session_state['staged_offers'])} Vendor Offer(s) Staged:**")
            st.caption("Confirm or type in the company name for each vendor offer below:")
            for o_name in list(st.session_state["staged_offers"].keys()):
                base_name = os.path.splitext(o_name)[0]
                for prefix in ["Vendor_Quote_", "Vendor_", "Quote_", "Offer_"]:
                    if base_name.lower().startswith(prefix.lower()):
                        parts = base_name.split("_")
                        base_name = parts[-1] if len(parts) > 1 else base_name
                
                curr_val = st.session_state["vendor_name_overrides"].get(o_name, base_name)
                vn_input = st.text_input(
                    f"Vendor Name for '{o_name}':",
                    value=curr_val,
                    key=f"vendor_override_{o_name}",
                    help=f"Type in the actual vendor/company name for '{o_name}'"
                )
                st.session_state["vendor_name_overrides"][o_name] = vn_input.strip() if vn_input else base_name

            if st.button("Clear Offers", key="btn_clear_offers"):
                st.session_state["staged_offers"] = {}
                st.session_state["vendor_name_overrides"] = {}
                st.rerun()

    with col3:
        st.markdown("### 3. Corporate Branding")
        st.caption("Upload from a folder or simply drag & drop files here.")
        logo_file = st.file_uploader(
            "Corporate Header / Logo (Optional Image)",
            type=["png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"],
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
        v_custom_name = st.session_state.get("vendor_name_overrides", {}).get(o_name, o_name)
        vendor_offers.append({"filename": o_name, "vendor_name": v_custom_name, "text": v_text})
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
    try:
        results = compare_spec_with_offers(
            spec_text, vendor_offers,
            user_preferences=user_prefs,
            specifier_company=st.session_state.get("specifier_company", "")
        )
    except Exception as e:
        status_box.empty()
        p1.empty()
        st.error(f"Compliance Audit Error: {str(e)}")
        st.info("Tip: Please verify that your LLM API key and model are properly configured in deployment secrets.")
        st.stop()
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
    specifier = results_to_display.get("specifier_company") or st.session_state.get("specifier_company")
    st.divider()
    st.header("Technical Compliance Audit Review")
    
    info_text = f"**Identified Project:** {project_name}"
    if specifier:
        info_text += f" &nbsp;&nbsp;|&nbsp;&nbsp; **Specifier / Engineer:** {specifier}"
    st.info(info_text)

    st.subheader("Executive Review Summary")
    exec_summary_text = results_to_display.get("executive_summary", "No executive summary provided.")
    st.markdown(exec_summary_text)

    # Specification Ambiguities & Clarification Callout
    ambiguities = results_to_display.get("specification_ambiguities", [])
    if ambiguities:
        st.warning("⚠️ **Specification Ambiguities & Human Clarification Schedule**")
        st.markdown(
            "*The specification contains the following ambiguous, contradictory, or incomplete clauses requiring verification by the consulting engineer:*"
        )
        amb_rows = []
        for a in ambiguities:
            amb_rows.append({
                "Scope Item / Equipment Area": a.get("item", "Specification"),
                "Specification Ambiguity Description": a.get("ambiguity", ""),
                "Engineering Impact": a.get("impact", ""),
                "Required Engineer Verification Action": a.get("verification_action", "")
            })
        st.dataframe(pd.DataFrame(amb_rows), use_container_width=True)

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
