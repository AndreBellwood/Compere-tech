import os
import time
import pandas as pd
import streamlit as st
from services.document_service import extract_document_text, extract_multiple_documents, clean_company_name
from services.ai_service import extract_document_parameters
from services.report_service import generate_extraction_pdf_report


def init_extraction_session_state():
    """Initializes session state keys for standalone parameter extraction."""
    if "staged_extract_docs" not in st.session_state:
        st.session_state["staged_extract_docs"] = {}
    if "extraction_results" not in st.session_state:
        st.session_state["extraction_results"] = None
    if "extract_pdf_bytes" not in st.session_state:
        st.session_state["extract_pdf_bytes"] = None
    if "extract_pdf_filename" not in st.session_state:
        st.session_state["extract_pdf_filename"] = "Parameter_Schedule.pdf"


def render_standalone_extraction():
    """Renders the Standalone Parameter Extraction Portal."""
    init_extraction_session_state()

    # Document Upload Section (Clearly demarcated, two shades darker background)
    with st.container(border=True):
        st.markdown("<span id='upload-section-marker'></span>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("### 1. Document Upload")
            st.caption("Upload from a folder or simply drag & drop files here.")
            extract_uploads = st.file_uploader(
                "Specification or Quotation (PDF, Word, Excel, TXT, Images)",
                type=["pdf", "docx", "xlsx", "xls", "txt", "csv", "rtf", "md", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"],
                accept_multiple_files=True,
                key="extract_uploader",
                help="Upload from a folder by clicking 'Browse files', or simply drag & drop files directly into this upload area."
            )
            if extract_uploads:
                for ef in extract_uploads:
                    st.session_state["staged_extract_docs"][ef.name] = ef.getvalue()

            if st.session_state["staged_extract_docs"]:
                st.success(f"**{len(st.session_state['staged_extract_docs'])} File(s) Staged:**")
                for e_name in list(st.session_state["staged_extract_docs"].keys()):
                    st.caption(f"• {e_name}")
                if st.button("Clear Document(s)", key="btn_clear_extract_docs"):
                    st.session_state["staged_extract_docs"] = {}
                    st.rerun()

        with col2:
            st.markdown("### 2. Document Nature")
            st.caption("Select specification, quotation, or auto-detect.")
            doc_type_option = st.selectbox(
                "Document Nature / Role",
                [
                    "Auto-Detect Document Nature",
                    "Consulting Engineering Specification / Equipment Schedule",
                    "Vendor Quotation / Equipment Tender Submission"
                ],
                key="extract_doc_type_select",
                help="Select whether this document represents an engineer's specification or a vendor quotation, or allow the AI to automatically detect its identity."
            )

        with col3:
            st.markdown("### 3. Corporate Branding")
            st.caption("Upload from a folder or simply drag & drop files here.")
            extract_logo_file = st.file_uploader(
                "Corporate Header / Logo (Optional Image)",
                type=["png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"],
                key="extract_logo_uploader",
                help="Upload from a folder by clicking 'Browse files', or simply drag & drop your corporate header or logo image here."
            )

    ready_to_extract = len(st.session_state["staged_extract_docs"]) > 0

    col_ex_exec, col_ex_dl = st.columns([1, 1])
    with col_ex_exec:
        btn_exec_extract = st.button("Extract & Tabulate HVAC Parameters", disabled=not ready_to_extract, key="btn_exec_extract", type="primary")

    with col_ex_dl:
        extract_dl_placeholder = st.empty()
        if st.session_state.get("extract_pdf_bytes"):
            extract_dl_placeholder.download_button(
                label="Download Corporate PDF Report",
                data=st.session_state["extract_pdf_bytes"],
                file_name=st.session_state.get("extract_pdf_filename", "Parameter_Schedule.pdf"),
                mime="application/pdf",
                key="btn_download_extract_top"
            )

    if btn_exec_extract:
        os.makedirs("uploads/standalone", exist_ok=True)
        status_box = st.empty()
        p1 = st.progress(0)

        with status_box.container():
            st.write("*Consolidating document files across formats...*")
        time.sleep(0.3)
        p1.progress(20)

        doc_paths = []
        for d_name, d_bytes in st.session_state["staged_extract_docs"].items():
            d_path = os.path.join("uploads", "standalone", d_name)
            with open(d_path, "wb") as f:
                f.write(d_bytes)
            doc_paths.append(d_path)

        primary_filename = os.path.basename(doc_paths[0]) if doc_paths else "Document"
        if len(doc_paths) == 1:
            extracted_text = extract_document_text(doc_paths[0])
        else:
            extracted_text = extract_multiple_documents(doc_paths)

        p1.progress(40)

        ex_logo_path = None
        if extract_logo_file:
            ex_logo_path = os.path.join("uploads", extract_logo_file.name)
            with open(ex_logo_path, "wb") as f:
                f.write(extract_logo_file.getvalue())

        hint = "auto"
        if "Specification" in doc_type_option:
            hint = "Specification"
        elif "Quotation" in doc_type_option:
            hint = "Vendor Quotation"

        with status_box.container():
            st.write("*Extracting HVAC parameters, equipment schedules, and engineering duties...*")

        user_prefs = st.session_state.get("user_preferences", {})
        extract_results = extract_document_parameters(
            extracted_text, filename=primary_filename, doc_type_hint=hint, user_preferences=user_prefs
        )
        p1.progress(80)

        with status_box.container():
            st.write("*Generating corporate parameter schedule PDF and layout...*")
        report_out = os.path.join("uploads", "Parameter_Schedule.pdf")
        generate_extraction_pdf_report(report_out, extract_results, ex_logo_path)

        with open(report_out, "rb") as f:
            ex_pdf_bytes = f.read()

        proj_name = extract_results.get("project_name", "HVAC Project")
        doc_type_clean = extract_results.get("document_type", "Schedule")
        clean_fname = f"{clean_company_name(proj_name)}_{clean_company_name(doc_type_clean)}_Schedule.pdf"

        st.session_state["extraction_results"] = extract_results
        st.session_state["extract_pdf_bytes"] = ex_pdf_bytes
        st.session_state["extract_pdf_filename"] = clean_fname

        extract_dl_placeholder.download_button(
            label="Download Corporate PDF Report",
            data=ex_pdf_bytes,
            file_name=clean_fname,
            mime="application/pdf",
            key="btn_download_extract_immediate"
        )

        p1.progress(100)
        status_box.empty()
        st.success("Parameter Extraction Complete.")

    ex_results = st.session_state.get("extraction_results")
    if ex_results:
        proj_name = ex_results.get("project_name", "HVAC Engineering Project")
        doc_nature = ex_results.get("document_type", "Engineering Document")
        entity_name = ex_results.get("entity_name", "Identified Entity")
        ref_num = ex_results.get("reference_number", "")

        st.divider()
        st.header(f"HVAC {doc_nature} Parameter Schedule Review")

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.metric(label="Identified Project", value=proj_name)
        with col_m2:
            st.metric(label="Document Nature", value=doc_nature)
        with col_m3:
            st.metric(label="Entity / Source", value=entity_name)
        with col_m4:
            st.metric(label="Reference #", value=ref_num if ref_num and ref_num.lower() != "n/a" else "—")

        st.subheader("Executive Technical Summary")
        exec_text = ex_results.get("executive_summary", "No executive summary provided.")
        st.markdown(exec_text)

        val_col_name = "Quoted / Offered Value" if "quote" in doc_nature.lower() else "Specified Requirement"

        scope_rows = ex_results.get("scope_table", [])
        if scope_rows:
            st.subheader("General Scope & Demarcation Matrix")
            flat_scope = []
            for r in scope_rows:
                flat_scope.append({
                    "Parameter": r.get("Parameter", ""),
                    val_col_name: r.get("Value", r.get("Spec_Requirement", r.get("Offer_Value", ""))),
                    "Engineering Criteria & Notes": r.get("Notes", r.get("Criteria", ""))
                })
            st.dataframe(pd.DataFrame(flat_scope), use_container_width=True)

        units = ex_results.get("units", [])
        if units:
            for unit in units:
                st.divider()
                st.subheader(unit.get("unit_name", "Equipment Unit Schedule"))
                unit_params = unit.get("parameters", [])
                if unit_params:
                    flat_params = []
                    for p in unit_params:
                        flat_params.append({
                            "Parameter": p.get("Parameter", ""),
                            val_col_name: p.get("Value", p.get("Spec_Requirement", p.get("Offer_Value", ""))),
                            "Engineering Criteria & Notes": p.get("Notes", p.get("Criteria", ""))
                        })
                    st.dataframe(pd.DataFrame(flat_params), use_container_width=True)

                t_notes = unit.get("technical_notes", [])
                if t_notes:
                    st.markdown("**Technical Notes & Equipment Observations:**")
                    if isinstance(t_notes, list):
                        for n in t_notes:
                            st.markdown(f"* {n}")
                    elif isinstance(t_notes, str):
                        st.markdown(f"* {t_notes}")
