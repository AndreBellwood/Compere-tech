import os
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4, portrait, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from PIL import Image as PILImage
from services.document_service import clean_company_name

def calculate_oadate(dt=None) -> float:
    """
    Calculates the OLE Automation Date (OADate).
    The base date epoch is midnight, 30 December 1899.
    """
    if dt is None:
        dt = datetime.now()
    epoch = datetime(1899, 12, 30)
    delta = dt - epoch
    return delta.days + (delta.seconds + delta.microseconds / 1e6) / 86400.0

def init_pdf_fonts():
    """
    Registers Arial Narrow font family if available on the system.
    Falls back gracefully to Helvetica if Arial Narrow is not present.
    Returns (FONT_NORMAL, FONT_BOLD, FONT_ITALIC, FONT_BOLD_ITALIC)
    """
    candidates = [
        ("C:/Windows/Fonts/ARIALN.TTF", "C:/Windows/Fonts/ARIALNB.TTF", "C:/Windows/Fonts/ARIALNI.TTF", "C:/Windows/Fonts/ARIALNBI.TTF"),
        ("C:/winnt/fonts/ARIALN.TTF", "C:/winnt/fonts/ARIALNB.TTF", "C:/winnt/fonts/ARIALNI.TTF", "C:/winnt/fonts/ARIALNBI.TTF"),
        ("C:/Windows/Fonts/arialn.ttf", "C:/Windows/Fonts/arialnb.ttf", "C:/Windows/Fonts/arialni.ttf", "C:/Windows/Fonts/arialnbi.ttf"),
    ]
    for norm_p, bold_p, ital_p, bi_p in candidates:
        if os.path.exists(norm_p) and os.path.exists(bold_p):
            try:
                pdfmetrics.registerFont(TTFont('ArialNarrow', norm_p))
                pdfmetrics.registerFont(TTFont('ArialNarrow-Bold', bold_p))
                pdfmetrics.registerFont(TTFont('ArialNarrow-Italic', ital_p if os.path.exists(ital_p) else norm_p))
                pdfmetrics.registerFont(TTFont('ArialNarrow-BoldItalic', bi_p if os.path.exists(bi_p) else bold_p))
                registerFontFamily(
                    'ArialNarrow',
                    normal='ArialNarrow',
                    bold='ArialNarrow-Bold',
                    italic='ArialNarrow-Italic',
                    boldItalic='ArialNarrow-BoldItalic'
                )
                return ('ArialNarrow', 'ArialNarrow-Bold', 'ArialNarrow-Italic', 'ArialNarrow-BoldItalic')
            except Exception:
                pass
    return ('Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique')

FONT_NORMAL, FONT_BOLD, FONT_ITALIC, FONT_BOLD_ITALIC = init_pdf_fonts()

class NumberedCanvas(canvas.Canvas):
    project_name = ""
    date_str = ""
    oadate_str = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count):
        self.saveState()
        pw, ph = self._pagesize
        left_x = 30
        right_x = pw - 30
        header_y = ph - 28
        line_y = ph - 36
        sub_hdr_y = ph - 48
        footer_line_y = 36
        footer_y = 24

        # Running Top Header (strictly >= 10 pt font)
        self.setFont(FONT_BOLD, 10)
        self.setFillColor(colors.HexColor("#1A365D"))
        self.drawString(left_x, header_y, "COMPèRE")
        compere_w = self.stringWidth("COMPèRE", FONT_BOLD, 10)

        self.setFont(FONT_NORMAL, 10)
        self.setFillColor(colors.HexColor("#4A5568"))
        pipe_str = "|   Technical Compliance Ledger"
        self.drawString(left_x + compere_w + 5, header_y, pipe_str)
        left_total_w = left_x + compere_w + 5 + self.stringWidth(pipe_str, FONT_NORMAL, 10)

        # Right header: Project title (flush right to right_x at >= 10 pt)
        proj_hdr = f"Project: {self.project_name}" if self.project_name else "HVAC Engineering Tender Adjudication"
        avail_w = right_x - left_total_w - 20

        self.setFont(FONT_NORMAL, 10)
        if self.stringWidth(proj_hdr, FONT_NORMAL, 10) > avail_w:
            trimmed = proj_hdr
            while len(trimmed) > 10 and self.stringWidth(trimmed + "...", FONT_NORMAL, 10) > avail_w:
                parts = trimmed.rsplit(' ', 1)
                if len(parts) > 1:
                    trimmed = parts[0]
                else:
                    trimmed = trimmed[:-1]
            proj_hdr = trimmed + "..."

        self.drawRightString(right_x, header_y, proj_hdr)

        # Top decorative rule line
        self.setStrokeColor(colors.HexColor("#CBD5E0"))
        self.setLineWidth(0.5)
        self.line(left_x, line_y, right_x, line_y)

        # Sub-header on top right just below the header dividing line (>= 10 pt)
        self.setFont(FONT_NORMAL, 10)
        self.setFillColor(colors.HexColor("#4A5568"))
        if self._pageNumber == 1:
            if self.date_str:
                self.drawRightString(right_x, sub_hdr_y, f"Date: {self.date_str}")
        else:
            if self.oadate_str:
                self.drawRightString(right_x, sub_hdr_y, f"Serial: {self.oadate_str}")

        # Bottom decorative rule line
        self.line(left_x, footer_line_y, right_x, footer_line_y)

        # Running Bottom Footer (strictly >= 10 pt font)
        self.setFont(FONT_NORMAL, 10)
        self.setFillColor(colors.HexColor("#718096"))
        self.drawString(left_x, footer_y, "Confidential — Prepared for Consulting Engineering Adjudication")
        self.drawRightString(right_x, footer_y, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()

def create_default_banner(styles, usable_w=535):
    title_style = ParagraphStyle(
        'BTitle', parent=styles['Normal'], fontName=FONT_BOLD,
        fontSize=16, leading=19, textColor=colors.whitesmoke
    )
    right_style = ParagraphStyle(
        'BRight', parent=styles['Normal'], fontName=FONT_BOLD,
        fontSize=10, leading=13, alignment=2, textColor=colors.whitesmoke
    )
    col1 = Paragraph("<b>COMPèRE</b><br/><font size=10 color='#90CDF4'>TECHNICAL COMPLIANCE TERMINAL</font>", title_style)
    col2 = Paragraph("HVAC ENGINEERING COMPLIANCE LEDGER<br/><font size=10 color='#CBD5E0'>INDEPENDENT TENDER ADJUDICATION REPORT</font>", right_style)
    
    w_right = 210 if usable_w < 600 else 252
    w_left = usable_w - w_right
    banner = Table([[col1, col2]], colWidths=[w_left, w_right])
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#1A365D")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    return banner

def get_status_color(status_str):
    s = str(status_str or "").lower()
    if any(w in s for w in ["non", "fail", "reject", "exclud"]):
        return "#C62828"
    elif any(w in s for w in ["marginal", "confirm", "tbc", "option", "oversiz"]):
        return "#D97706"
    elif any(w in s for w in ["compliant", "pass", "meet"]):
        return "#2E7D32"
    return "#4A5568"

def make_cell(text, style, color=None):
    text_str = str(text or "").strip()
    if not text_str or text_str == "—":
        return Paragraph("<font color='#A0AEC0'>—</font>", style)
    clean = text_str.replace('\n', '<br/>')
    if color:
        return Paragraph(f"<font color='{color}'><b>{clean}</b></font>", style)
    return Paragraph(clean, style)

def build_leaderboard_table(vendor_scores, usable_w):
    """
    Renders the Executive Vendor Compliance Leaderboard on Page 1.
    Columns: Vendor Offer / Submission, Compliance %, Passed, Marginal / TBC, Failed.
    Formatted to fit exact usable width with text strictly >= 10 pt.
    """
    hdr_style = ParagraphStyle('LdHdr', fontName=FONT_BOLD, fontSize=10, leading=13, textColor=colors.whitesmoke)
    row_style = ParagraphStyle('LdRow', fontName=FONT_NORMAL, fontSize=10, leading=13, textColor=colors.HexColor("#2D3748"))
    
    table_data = [[
        Paragraph("<b>Vendor Offer / Submission</b>", hdr_style),
        Paragraph("<b>Compliance %</b>", hdr_style),
        Paragraph("<b>Passed</b>", hdr_style),
        Paragraph("<b>Marginal / TBC</b>", hdr_style),
        Paragraph("<b>Failed</b>", hdr_style)
    ]]
    for v in vendor_scores:
        c_name = clean_company_name(v.get("vendor_name", "Vendor"))
        pct = v.get("compliance_percent", 0.0)
        c = "#2E7D32" if pct >= 80 else ("#D97706" if pct >= 50 else "#C62828")
        table_data.append([
            Paragraph(f"<b>{c_name}</b>", row_style),
            Paragraph(f"<font color='{c}'><b>{pct}%</b></font>", row_style),
            Paragraph(str(v.get("passed_count", 0)), row_style),
            Paragraph(str(v.get("marginal_count", 0)), row_style),
            Paragraph(str(v.get("failed_count", 0)), row_style)
        ])

    if usable_w < 600:
        w_stat = 78
        w_comp = usable_w - (w_stat * 4)
        col_widths = [w_comp, w_stat, w_stat, w_stat, w_stat]
    else:
        w_stat = 115
        w_comp = usable_w - (w_stat * 4)
        col_widths = [w_comp, w_stat, w_stat, w_stat, w_stat]

    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A365D")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    return t


def build_parameter_tables(rows, vendor_scores, styles, cell_style, header_style, usable_w=535, is_landscape=False):
    """
    Constructs multi-vendor comparison tables chunked into batches.
    Total width of each table strictly matches usable_w with text strictly >= 10 pt.
    """
    if not rows:
        return []
        
    has_vendors_dict = any("vendors" in r for r in rows)
    if not has_vendors_dict:
        # Legacy fallback
        content = [[
            Paragraph("<b>Parameter</b>", header_style),
            Paragraph("<b>Specification Requirement</b>", header_style),
            Paragraph("<b>Supplier Offer</b>", header_style),
            Paragraph("<b>Status</b>", header_style)
        ]]
        for r in rows:
            st_val = r.get("Status", "")
            c = get_status_color(st_val)
            content.append([
                make_cell(r.get("Parameter", ""), cell_style),
                make_cell(r.get("Spec_Requirement", ""), cell_style),
                make_cell(r.get("Offer_Value", ""), cell_style, color=c),
                Paragraph(f"<font color='{c}'><b>{st_val}</b></font>", cell_style)
            ])
        w_p = int(usable_w * 0.28)
        w_s = int(usable_w * 0.28)
        w_o = int(usable_w * 0.28)
        w_st = usable_w - (w_p + w_s + w_o)
        t = Table(content, colWidths=[w_p, w_s, w_o, w_st])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A365D")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        return [t]

    score_map = {}
    vendor_names = []
    for v in (vendor_scores or []):
        cname = clean_company_name(v.get("vendor_name", ""))
        score_map[cname] = v.get("compliance_percent", 0.0)
        if cname and cname not in vendor_names:
            vendor_names.append(cname)

    if not vendor_names:
        for r in rows:
            for k in r.get("vendors", {}).keys():
                cname = clean_company_name(k)
                if cname and cname not in vendor_names:
                    vendor_names.append(cname)

    chunk_size = 5 if is_landscape else 4
    chunks = [vendor_names[i:i + chunk_size] for i in range(0, len(vendor_names), chunk_size)]
    tables = []

    for c_idx, chunk in enumerate(chunks):
        num_v = len(chunk)
        w_param = 115 if usable_w < 600 else 135
        w_spec = 108 if usable_w < 600 else 125
        w_rem = usable_w - (w_param + w_spec)
        w_v = int(w_rem / num_v)
        col_widths = [usable_w - (w_spec + w_v * num_v), w_spec] + [w_v] * num_v

        hdr_row = [
            Paragraph("<b>Parameter</b>", header_style),
            Paragraph("<b>Specification Requirement</b>", header_style)
        ]
        for vn in chunk:
            score = score_map.get(vn, 0.0)
            sc_color = "#90CDF4" if score >= 80 else ("#F6E05E" if score >= 50 else "#FEB2B2")
            hdr_text = f"<b>{vn}</b><br/><font size=10 color='{sc_color}'><b>{score}%</b></font>"
            hdr_row.append(Paragraph(hdr_text, header_style))

        content = [hdr_row]
        for r in rows:
            p_name = r.get("Parameter", "")
            spec_val = r.get("Spec_Requirement", "")
            row_cells = [
                make_cell(p_name, cell_style),
                make_cell(spec_val, cell_style)
            ]
            v_map = r.get("vendors", {})
            clean_v_map = {clean_company_name(k): val for k, val in v_map.items()}

            for vn in chunk:
                v_entry = clean_v_map.get(vn, v_map.get(vn, {}))
                val = str(v_entry.get("value", "")).strip()
                st_val = str(v_entry.get("status", "")).strip()
                c = get_status_color(st_val)
                if not val or val == "—":
                    row_cells.append(Paragraph("<font color='#A0AEC0'>—</font>", cell_style))
                else:
                    tag_str = f"<br/><font size=10 color='{c}'>[{st_val}]</font>" if st_val else ""
                    cell_html = f"<font color='{c}'><b>{val}</b></font>{tag_str}"
                    row_cells.append(Paragraph(cell_html, cell_style))
            content.append(row_cells)

        t = Table(content, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A365D")),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        tables.append(t)

    return tables


def generate_pdf_report(output_filename, data, logo_path=None):
    # Determine number of vendor columns
    vendor_names = []
    for v in data.get("vendor_scores", []):
        vn = clean_company_name(v.get("vendor_name", ""))
        if vn and vn not in vendor_names:
            vendor_names.append(vn)

    for c in data.get("offer_columns", []):
        vn = clean_company_name(c)
        if vn and vn not in vendor_names:
            vendor_names.append(vn)

    for r in data.get("scope_table", []):
        for k in r.get("vendors", {}).keys():
            vn = clean_company_name(k)
            if vn and vn not in vendor_names:
                vendor_names.append(vn)

    for unit in data.get("units", []):
        for p in unit.get("parameters", []):
            for k in p.get("vendors", {}).keys():
                vn = clean_company_name(k)
                if vn and vn not in vendor_names:
                    vendor_names.append(vn)

    num_vendors = len(vendor_names)
    # A4 portrait mode UNLESS there are more than 4 vendor columns (then landscape)
    is_landscape = (num_vendors > 4)
    pagesize = landscape(A4) if is_landscape else portrait(A4)
    pw, ph = pagesize
    margin = 30
    usable_w = pw - (margin * 2)

    # Date and OADate serial calculation
    dt_now = datetime.now()
    date_str = f"{dt_now.day} {dt_now.strftime('%B %Y')}"
    oadate_val = calculate_oadate(dt_now)
    oadate_str = f"{oadate_val:.1f}"

    doc = SimpleDocTemplate(
        output_filename, pagesize=pagesize,
        leftMargin=margin, rightMargin=margin, topMargin=58, bottomMargin=48
    )
    story = []
    styles = getSampleStyleSheet()

    # All typography strictly >= 10 point font
    cell_style = ParagraphStyle(
        'GCell', parent=styles['Normal'], fontName=FONT_NORMAL,
        fontSize=10, leading=13, textColor=colors.HexColor("#2D3748")
    )
    header_style = ParagraphStyle(
        'GHeader', parent=styles['Normal'], fontName=FONT_BOLD,
        fontSize=10, leading=13, textColor=colors.whitesmoke
    )
    unit_title_style = ParagraphStyle(
        'UTitle', parent=styles['Heading1'], fontName=FONT_BOLD,
        fontSize=13, leading=16, textColor=colors.HexColor("#1A365D"), spaceAfter=3
    )
    exec_style = ParagraphStyle(
        'ExecStyle', parent=styles['Normal'], fontName=FONT_NORMAL,
        fontSize=10, leading=13.5, textColor=colors.HexColor("#2D3748"), spaceAfter=3
    )
    h1_style = ParagraphStyle(
        'RepH1', parent=styles['Heading1'], fontName=FONT_BOLD,
        fontSize=14, leading=18, textColor=colors.HexColor("#1A365D"), spaceAfter=4
    )
    h2_style = ParagraphStyle(
        'RepH2', parent=styles['Heading2'], fontName=FONT_BOLD,
        fontSize=11.5, leading=15, textColor=colors.HexColor("#1A365D"), spaceAfter=3
    )
    note_title_style = ParagraphStyle(
        'NoteTitle', parent=styles['Normal'], fontName=FONT_BOLD,
        fontSize=10, leading=13, textColor=colors.HexColor("#1A365D"), spaceAfter=2
    )
    note_body_style = ParagraphStyle(
        'NoteBody', parent=styles['Normal'], fontName=FONT_NORMAL,
        fontSize=10, leading=13, textColor=colors.HexColor("#2D3748"), spaceAfter=2
    )
    continued_style = ParagraphStyle(
        'RepCont', parent=styles['Normal'], fontName=FONT_ITALIC,
        fontSize=10, leading=13, textColor=colors.HexColor("#718096"), spaceAfter=3
    )

    v_scores = data.get("vendor_scores", [])

    # ─── PAGE 1: HEADER, READABLE EXECUTIVE SUMMARY & LEADERBOARD ───
    if logo_path and os.path.exists(logo_path):
        with PILImage.open(logo_path) as img:
            orig_w, orig_h = img.size
        target_w = usable_w
        scale = target_w / float(orig_w)
        target_h = orig_h * scale
        if target_h > 55:
            target_h = 55
            scale = target_h / float(orig_h)
            target_w = orig_w * scale
        story.append(Image(logo_path, width=target_w, height=target_h))
    else:
        story.append(create_default_banner(styles, usable_w))
        
    story.append(Spacer(1, 8))
    story.append(Paragraph("HVAC Engineering Compliance Ledger", h1_style))
    story.append(Spacer(1, 3))
    
    project_title = str(data.get("project_name", "")).strip()
    proj_style = ParagraphStyle(
        'ProjStyle', parent=styles['Normal'], fontName=FONT_BOLD,
        fontSize=10.5, leading=14, textColor=colors.HexColor("#1A365D"), spaceAfter=3
    )
    meta_parts = []
    if project_title and project_title.lower() != "unknown":
        meta_parts.append(f"<b>Project:</b> {project_title}")
    meta_parts.append(f"<b>Date:</b> {date_str}")
    meta_text = " &nbsp;&nbsp;|&nbsp;&nbsp; ".join(meta_parts)
    story.append(Paragraph(meta_text, proj_style))
    story.append(Spacer(1, 3))

    story.append(Paragraph("Executive Review Summary", h2_style))
    story.append(Spacer(1, 2))

    # Render Executive Summary as readable paragraphs with bold headings (all >= 10 pt)
    exec_raw = str(data.get("executive_summary", "No executive summary provided.")).strip()
    exec_blocks = [b.strip() for b in exec_raw.split('\n') if b.strip()]
    for b in exec_blocks:
        b_html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', b)
        story.append(Paragraph(b_html, exec_style))
        story.append(Spacer(1, 2))
    story.append(Spacer(1, 5))
    
    if v_scores:
        story.append(Paragraph("Vendor Compliance Adjudication Leaderboard", h2_style))
        story.append(Spacer(1, 3))
        story.append(build_leaderboard_table(v_scores, usable_w))
        story.append(Spacer(1, 6))
        
    # PAGE 1 ENDS HERE
    story.append(PageBreak())

    # ─── PAGE 2: GENERAL SCOPE & DEMARCATION MATRIX ───
    scope_rows = data.get("scope_table", [])
    if scope_rows:
        story.append(Paragraph("General Scope & Demarcation Matrix", h1_style))
        story.append(Spacer(1, 5))
        scope_tables = build_parameter_tables(scope_rows, v_scores, styles, cell_style, header_style, usable_w, is_landscape)
        for idx, stbl in enumerate(scope_tables):
            if idx > 0:
                story.append(Spacer(1, 4))
                story.append(Paragraph("<i>(General Scope Continued - Additional Submissions)</i>", continued_style))
                story.append(Spacer(1, 3))
            story.append(stbl)
        story.append(Spacer(1, 8))

    # ─── PAGE 3 ONWARDS: EACH UNIT ON ITS OWN PAGE ───
    units = data.get("units", [])
    if units:
        for unit in units:
            story.append(PageBreak())
            story.append(Paragraph(unit.get("unit_name", "Equipment Unit Review"), unit_title_style))
            story.append(Spacer(1, 5))
            unit_params = unit.get("parameters", [])
            if unit_params:
                story.append(Paragraph("Technical Parameter Matrix", h2_style))
                story.append(Spacer(1, 3))
                param_tables = build_parameter_tables(unit_params, v_scores, styles, cell_style, header_style, usable_w, is_landscape)
                for p_idx, ptbl in enumerate(param_tables):
                    if p_idx > 0:
                        story.append(Spacer(1, 4))
                        story.append(Paragraph("<i>(Technical Parameters Continued - Additional Submissions)</i>", continued_style))
                        story.append(Spacer(1, 3))
                    story.append(ptbl)
                story.append(Spacer(1, 6))
            disc = unit.get("discrepancies", {})
            if disc:
                story.append(Paragraph("Technical Notes & Specific Discrepancies", h2_style))
                story.append(Spacer(1, 3))
                if isinstance(disc, dict):
                    for raw_vn, notes in disc.items():
                        c_vn = clean_company_name(raw_vn)
                        story.append(Paragraph(f"<b>{c_vn}:</b>", note_title_style))
                        for n in notes:
                            story.append(Paragraph(f"• {n}", note_body_style))
                elif isinstance(disc, list):
                    for n in disc:
                        story.append(Paragraph(f"• {n}", note_body_style))

    class ProjectNumberedCanvas(NumberedCanvas):
        pass

    ProjectNumberedCanvas.project_name = project_title
    ProjectNumberedCanvas.date_str = date_str
    ProjectNumberedCanvas.oadate_str = oadate_str

    doc.build(story, canvasmaker=ProjectNumberedCanvas)
