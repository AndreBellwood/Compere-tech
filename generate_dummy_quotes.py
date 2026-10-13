import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

BASE_TECH = [
    ("Supply Airflow", "5300 l/s", "5300 l/s", "Design match"),
    ("External Static Pressure", "1000 Pa", "1000 Pa", "Design match"),
    ("Fan Arrangement", "2x EC500 Plug fans", "2x ebm-papst EC500 Plug fans", "ebm-papst FanGrid array"),
    ("Fan Power Input", "8382 W (8.4 kW)", "8382 W", "400V / 3Ph / 50Hz"),
    ("Cooling Coil Capacity", "56.4 kW", "56.4 kW", "Dry expansion DX coil R410A"),
    ("Entering Air Conditions", "22.0 °C DB / 15.7 °C WB", "22.0 °C DB / 15.7 °C WB", "Design match"),
    ("Leaving Air Conditions", "14.5 °C DB / 12.3 °C WB", "14.5 °C DB / 12.3 °C WB", "Design match"),
    ("DX Coil Materials", "SS casing, Cu tubes, Al fins", "SS304 casing, Cu tubes, Al fins", "8 passes, 185 m²"),
    ("Condensate Drip Tray", "1.2mm SS V-shape sloped", "1.2mm 304 SS V-shape sloped", "Center drain Ø28mm"),
    ("Base Frame", "100 x 50 galv channel", "100 x 50mm Galv channel", "Bolted tapered flange"),
    ("Panels & Insulation", "50mm Chromadek double-skin", "50mm Chromadek double-skin", "Polystyrene insulated"),
    ("Primary Filtration", "G4 / EU4 (50mm washable)", "G4 Primary washable panel (50mm)", "6x 592x592 & 3x 592x292"),
    ("Secondary Filtration", "F8 Bag Filter (300mm soft)", "F8 Soft Bag Filter (300mm)", "6x 592x592 & 3x 592x292"),
    ("Differential Gauge", "Magnehelic gauge fitted", "Dwyer Magnehelic gauge fitted", "Across filter banks"),
    ("Electrical & Controls", "Isolator, E-Stop, lights, panel", "Isolator, E-Stop, lights, panel", "Pre-wired factory panel"),
    ("VRF Interface Kit", "VRF kit fitment", "VRF interface kit fitted", "Ready for VRF condenser"),
    ("Sloped Weather Roof", "90mm to 50mm slope", "90mm to 50mm sloped roof", "Weather cowl fitted"),
    ("Unit Weight", "1155 kg approx", "1165 kg approx", "Verified engineering weight")
]
def make_quote_pdf(filepath, vendor_info, overrides, comm_items):
    doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()
    c = vendor_info['color']
    
    v_hdr = ParagraphStyle('VHdr', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=colors.HexColor(c))
    v_sub = ParagraphStyle('VSub', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor("#4A5568"))
    ref_s = ParagraphStyle('Ref', fontName='Helvetica-Bold', fontSize=8.5, leading=12, alignment=2, textColor=colors.HexColor("#2D3748"))
    s_title = ParagraphStyle('STitle', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.HexColor(c), spaceAfter=4)
    body = ParagraphStyle('Body', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor("#2D3748"))
    t_hdr = ParagraphStyle('THdr', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.whitesmoke)
    t_cell = ParagraphStyle('TCell', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=colors.HexColor("#2D3748"))

    l_box = Paragraph(f"<b>{vendor_info['company']}</b><br/><font size=7 color='#718096'>{vendor_info['address']}<br/>Tel: {vendor_info['tel']} | {vendor_info['email']}</font>", v_sub)
    r_box = Paragraph(f"<b>OFFICIAL TENDER QUOTATION</b><br/><b>Ref:</b> {vendor_info['quote_ref']}<br/><b>Date:</b> {vendor_info['date']}<br/><b>Validity:</b> 30 Days", ref_s)
    top_t = Table([[Paragraph(f"<b>{vendor_info['company']}</b>", v_hdr), r_box]], colWidths=[340, 200])
    top_t.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    story.append(top_t)
    story.append(l_box)
    story.append(Spacer(1, 6))

    bar = Table([[""]], colWidths=[540], rowHeights=[2])
    bar.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor(c)), ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0)]))
    story.append(bar)
    story.append(Spacer(1, 8))

    proj = "<b>Client:</b> Sasol Synfuels Engineers | <b>Project:</b> SASOL Phase 1 Expansion<br/><b>Equipment Tag:</b> UNIT 2 - Air Handling Unit Package (Approval Pack Spec)"
    story.append(Paragraph(proj, body))
    story.append(Spacer(1, 8))

    story.append(Paragraph("1. Technical Performance Schedule", s_title))
    tbl_rows = [[Paragraph("<b>Parameter</b>", t_hdr), Paragraph("<b>Spec Requirement</b>", t_hdr), Paragraph(f"<b>Offered by {vendor_info['short_name']}</b>", t_hdr), Paragraph("<b>Technical Note</b>", t_hdr)]]
    for row in BASE_TECH:
        param_name, spec_val, default_offered, default_note = row
        offered, note = overrides.get(param_name, (default_offered, default_note))
        tbl_rows.append([Paragraph(param_name, t_cell), Paragraph(spec_val, t_cell), Paragraph(f"<b>{offered}</b>", t_cell), Paragraph(note, t_cell)])
        
    t_tech = Table(tbl_rows, colWidths=[120, 115, 155, 150])
    t_tech.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(c)),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_tech)
    story.append(Spacer(1, 8))

    story.append(Paragraph("2. Commercial Pricing & Scope Demarcation", s_title))
    c_rows = [[Paragraph("<b>Scope Item</b>", t_hdr), Paragraph("<b>Terms / Clarification</b>", t_hdr), Paragraph("<b>Amount (ZAR excl. VAT)</b>", t_hdr)]]
    for ci in comm_items:
        c_rows.append([Paragraph(ci[0], t_cell), Paragraph(ci[1], t_cell), Paragraph(f"<b>{ci[2]}</b>", t_cell)])
    t_comm = Table(c_rows, colWidths=[170, 240, 130])
    t_comm.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor(c)),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_comm)
    story.append(Spacer(1, 6))

    closing = f"<b>Authorized Representative:</b> {vendor_info['rep']} | <i>Technical Sales Division</i> (E&OE)"
    story.append(Paragraph(closing, body))
    doc.build(story)
    print(f"Generated: {filepath}")


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    ts_dir = os.path.join(out_dir, "Test_Suite")
    os.makedirs(ts_dir, exist_ok=True)
    
    # V1: ThermOpac (High Compliance)
    v1 = {
        'company': "ThermOpac Air Systems (Pty) Ltd", 'short_name': "ThermOpac",
        'color': "#1A365D", 'address': "12 Factory Rd, Meadowdale, Johannesburg",
        'tel': "+27 11 974 8100", 'email': "sales@thermopac.co.za",
        'quote_ref': "TOP-2026-SAS-002-R1", 'date': "18 March 2026",
        'rep': "Johan van der Merwe, Pr.Eng"
    }
    v1_over = {}
    v1_comm = [
        ["AHU Unit 2 Manufacture", "Complete with controls & DX coil", "R 348,500.00"],
        ["Delivery to Site (Sasol)", "Road freight to Secunda roadside", "Included"],
        ["Off-loading & Craneage", "By Mechanical Rigging Contractor", "Excluded (By others)"]
    ]

    # V2: Carrier (Good Compliance + Optional VRF Kit)
    v2 = {
        'company': "Carrier Commercial HVAC Solutions", 'short_name': "Carrier",
        'color': "#003A70", 'address': "5 Constantia Park, Midrand, South Africa",
        'tel': "+27 11 805 8300", 'email': "quotes@carrier-sa.co.za",
        'quote_ref': "CAR-SEC-2026-904", 'date': "19 March 2026",
        'rep': "Bradley Peters, B.Sc. Mech"
    }
    v2_over = {
        "Supply Airflow": ("5350 l/s", "Minor positive variance (+0.9%)"),
        "Fan Arrangement": ("2x Ziehl-Abegg ECblue 500mm fans", "Equivalent EC plug array"),
        "Cooling Coil Capacity": ("58.2 kW", "Slight over-capacity (+3.2%)"),
        "Secondary Filtration": ("F7 Bag Filter (300mm soft)", "F7 offered instead of F8 (Marginal)"),
        "VRF Interface Kit": ("Optional Extra (+R 14,800)", "Quoted as optional add-on (Marginal)")
    }
    v2_comm = [
        ["Carrier 39HQ Base AHU", "Standard unit with electrical panel", "R 362,000.00"],
        ["VRF Interface Kit", "Pre-piped and wired in cubicle", "R 14,800.00 (Optional)"],
        ["Delivery to Site", "Delivered roadside Secunda", "Included"]
    ]

    # V3: Trane (Oversized Coil 66.5 kW + Ex-Works)
    v3 = {
        'company': "Trane Commercial Systems South Africa", 'short_name': "Trane",
        'color': "#D97706", 'address': "Plot 18, Corporate Park South, Midrand",
        'tel': "+27 11 203 0600", 'email': "tenders@trane.co.za",
        'quote_ref': "TRN-SAS-AHU2-2026", 'date': "16 March 2026",
        'rep': "Craig Thomson, Commercial Engineer"
    }
    v3_over = {
        "External Static Pressure": ("950 Pa", "Minor deficit (-50 Pa / -5%)"),
        "Cooling Coil Capacity": ("66.5 kW", "Oversized by 17.9% (>15% Marginal/Review)"),
        "DX Coil Materials": ("Galv casing, Cu tubes, Al fins", "Galvanized coil casing (Spec: SS)"),
        "Panels & Insulation": ("50mm Rockwool (Chromadek/Galv)", "Galvanized inner skin (Spec: Chromadek)"),
        "Electrical & Controls": ("Isolator & panel (Lights optional)", "Plenum lights & E-Stop optional (Marginal)")
    }
    v3_comm = [
        ["Trane Unit 2 AHU Package", "Ex-works Johannesburg factory", "R 335,000.00"],
        ["Plenum Lights & E-Stop Kit", "Chamber lighting + E-Stop push", "R 9,500.00 (Optional)"],
        ["Transport to Secunda Site", "Factory collection only (Ex-Works)", "Excluded (R 18,500 extra)"]
    ]
    # V4: Daikin (Minor Deficits & VRF Excluded)
    v4 = {
        'company': "Daikin Applied South Africa (Pty) Ltd", 'short_name': "Daikin",
        'color': "#0097A7", 'address': "15 Kelly Rd, Jet Park, Boksburg",
        'tel': "+27 11 997 1300", 'email': "quotes@daikinapplied.co.za",
        'quote_ref': "DA-SEC-26-U2-REV0", 'date': "17 March 2026",
        'rep': "Markus Engelbrecht, Specialist"
    }
    v4_over = {
        "Supply Airflow": ("5200 l/s", "Minor deficit (-1.9% within tolerance)"),
        "Cooling Coil Capacity": ("55.0 kW", "Minor duty deficit (-2.5%)"),
        "DX Coil Materials": ("Galvanized casing, Cu/Al fins", "Galvanized casing (Spec SS)"),
        "VRF Interface Kit": ("Excluded (By VRF contractor)", "Non-compliant (VRF kit omitted)")
    }
    v4_comm = [
        ["Daikin D-AHU Unit 2", "Manufactured and factory tested", "R 354,200.00"],
        ["Delivery to Secunda Site", "Delivered roadside Secunda", "Included"],
        ["VRF Expansion Kit", "Omitted (by VRF vendor)", "Excluded"]
    ]

    # V5: AirCraft (Budget / Non-Compliant Low Score)
    v5 = {
        'company': "AirCraft HVAC Manufacturing (Pty) Ltd", 'short_name': "AirCraft",
        'color': "#9B1C1C", 'address': "44 Foundry Rd, Silverton, Pretoria",
        'tel': "+27 12 804 1200", 'email': "sales@aircrafthvac.co.za",
        'quote_ref': "AC-2026-SAS-T2", 'date': "15 March 2026",
        'rep': "Leon Botha, Estimator"
    }
    v5_over = {
        "Supply Airflow": ("4900 l/s", "Non-compliant deficit (-7.5%)"),
        "External Static Pressure": ("800 Pa", "Non-compliant deficit (-200 Pa)"),
        "Fan Arrangement": ("1x Belt-driven Centrifugal Fan", "Non-compliant (Spec: 2x EC Plug fans)"),
        "Fan Power Input": ("11000 W (11 kW induction)", "Higher energy consumption"),
        "Cooling Coil Capacity": ("48.0 kW", "Non-compliant deficit (-14.9%)"),
        "Panels & Insulation": ("25mm Polystyrene panels", "Non-compliant (25mm vs 50mm spec)"),
        "Secondary Filtration": ("Excluded (Not fitted)", "Non-compliant (F8 bags omitted)"),
        "Electrical & Controls": ("Isolator only (Panel excluded)", "Non-compliant (Panel omitted)"),
        "VRF Interface Kit": ("Excluded", "Non-compliant (No VRF kit)"),
        "Sloped Weather Roof": ("Flat roof silicone sealed", "Non-compliant (Flat roof)")
    }
    v5_comm = [
        ["AirCraft Economy AHU Unit 2", "Bare unit ex-factory Silverton", "R 245,000.00"],
        ["Electrical Control Panel", "Excluded", "R 35,000.00 (Optional)"],
        ["Delivery to Site", "Ex-Works factory Pretoria", "Excluded (By client)"]
    ]

    quotes = [
        ("Vendor_Quote_1_ThermOpac.pdf", v1, v1_over, v1_comm),
        ("Vendor_Quote_2_Carrier.pdf", v2, v2_over, v2_comm),
        ("Vendor_Quote_3_Trane.pdf", v3, v3_over, v3_comm),
        ("Vendor_Quote_4_Daikin.pdf", v4, v4_over, v4_comm),
        ("Vendor_Quote_5_AirCraft.pdf", v5, v5_over, v5_comm)
    ]

    for fname, info, over, comm in quotes:
        p1 = os.path.join(out_dir, fname)
        make_quote_pdf(p1, info, over, comm)
        p2 = os.path.join(ts_dir, fname)
        make_quote_pdf(p2, info, over, comm)

if __name__ == "__main__":
    main()

