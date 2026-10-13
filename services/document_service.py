import os
import zipfile
import xml.etree.ElementTree as ET
import fitz  # PyMuPDF
from markitdown import MarkItDown
import pandas as pd

def extract_excel_text(file_path: str) -> str:
    """Reads all sheets from Excel spreadsheets into clean tables."""
    try:
        excel_file = pd.ExcelFile(file_path)
        chunks = []
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            df = df.dropna(how='all')
            if not df.empty:
                chunks.append(f"Sheet: {sheet_name}\n" + df.to_string(index=False))
        return "\n\n".join(chunks)
    except Exception:
        return ""

def extract_docx_fallback(file_path: str) -> str:
    """Fallback extraction for .docx files via native XML parsing."""
    try:
        with zipfile.ZipFile(file_path) as z:
            xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            paragraphs = []
            for node in tree.iter():
                if node.tag.endswith('}p'):
                    texts = [t.text for t in node.iter() if t.tag.endswith('}t') and t.text]
                    if texts:
                        paragraphs.append("".join(texts))
            return "\n".join(paragraphs)
    except Exception:
        return ""

def extract_document_text(file_path: str) -> str:
    """
    Parses layout text, engineering grid tables, and spreadsheets.
    Supports PDF, DOCX, XLSX, XLS, CSV, TXT with multi-tier fallbacks.
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    # 1. First attempt: MarkItDown (Microsoft layout-aware engine)
    try:
        md = MarkItDown()
        result = md.convert(file_path)
        if result and result.text_content and len(result.text_content.strip()) > 20:
            return result.text_content
    except Exception:
        pass

    # 2. Format-specific fallbacks
    if ext in ['.xlsx', '.xls']:
        text = extract_excel_text(file_path)
        if text:
            return text

    if ext == '.docx':
        text = extract_docx_fallback(file_path)
        if text:
            return text

    if ext in ['.txt', '.csv', '.rtf', '.md']:
        for enc in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(file_path, 'r', encoding=enc, errors='ignore') as f:
                    return f.read()
            except Exception:
                continue

    # 3. PDF Fallback via PyMuPDF (fitz)
    text = ""
    try:
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text() + "\n"
    except Exception:
        pass
        
    return text

def extract_multiple_documents(file_paths: list[str]) -> str:
    """
    Consolidates text from multiple specification or offer documents.
    """
    consolidated = []
    for idx, path in enumerate(file_paths, start=1):
        fname = os.path.basename(path)
        doc_text = extract_document_text(path)
        consolidated.append(f"=== SPECIFICATION COMPONENT {idx}: {fname} ===\n{doc_text}\n")
    return "\n\n".join(consolidated)

def extract_document_clues(text: str, filename: str = "") -> dict:
    """
    Extracts structural identification clues from raw document text:
    - Email addresses & corporate email domains
    - Document header lines
    - Explicit project names / client markers
    - Quote reference numbers
    - Offer options / tier indications (Premium, Budget, Option 1, Option 2, etc.)
    """
    clues = {
        "filename": filename,
        "emails": [],
        "domains": [],
        "project_candidates": [],
        "quote_refs": [],
        "tier_hints": [],
        "header_snippet": ""
    }
    
    if not text:
        return clues

    # 1. Email extraction and corporate domain identification
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)
    full_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    generic_domains = {'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'mail.com'}
    
    unique_domains = []
    for d in emails:
        d_lower = d.lower()
        if d_lower not in generic_domains:
            primary = d_lower.split('.')[0]
            if primary and primary not in unique_domains:
                unique_domains.append(primary)
                
    clues["emails"] = list(dict.fromkeys(full_emails))[:5]
    clues["domains"] = unique_domains[:3]

    # 2. Project / Tender / Client references
    proj_patterns = [
        r'(?:Project|Tender|Contract|Client|Site)\s*[:\-]\s*([^\n\r|]{3,60})',
        r'Re\s*:\s*([^\n\r|]{3,60})'
    ]
    for pat in proj_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            cleaned = m.group(1).strip()
            if len(cleaned) > 2 and not cleaned.lower().startswith(('the tenderer', 'quotation', 'date', 'page')):
                if cleaned not in clues["project_candidates"]:
                    clues["project_candidates"].append(cleaned)

    # 3. Quotation Reference patterns
    ref_matches = re.findall(r'(?:Ref|Quote\s*(?:No|Ref|#)?|Quotation\s*(?:No|Ref|#)?)\s*[:\-#]\s*([A-Za-z0-9\-_\/]{4,30})', text, re.IGNORECASE)
    clues["quote_refs"] = list(dict.fromkeys(ref_matches))[:4]

    # 4. Detect tier indicators
    tier_keywords = ["premium", "budget", "option 1", "option 2", "option a", "option b", "alternative", "base offer", "economy"]
    found_tiers = []
    text_lower = text.lower()
    for kw in tier_keywords:
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            found_tiers.append(kw.title())
    clues["tier_hints"] = list(dict.fromkeys(found_tiers))

    # 5. Header snippet (first 15 non-empty lines)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clues["header_snippet"] = "\n".join(lines[:15])

    return clues


import re

def clean_company_name(raw: str) -> str:
    """
    String hygiene to format vendor / offer column labels into clean, readable titles.
    - Strips extensions, file noise, and trailing duplicate revision numbers.
    - Cleans generic corporate legal suffixes while preserving offer qualifications.
    - Preserves internal camel-case capitalization (e.g. ThermOpac, AirCraft).
    """
    name = str(raw or "").strip()
    if not name:
        return "Vendor"

    for ext in ['.pdf', '.docx', '.xlsx', '.xls', '.txt', '.csv', '.rtf', '.md']:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]

    tier_match = re.search(r'\s*(\((?:Premium|Budget|Option\s*[0-9A-Za-z]|Alternative|Standard|Base|Economy)[^\)]*\))\s*$', name, flags=re.IGNORECASE)
    tier_suffix = ""
    if tier_match:
        tier_suffix = f" {tier_match.group(1).strip()}"
        name = name[:tier_match.start()].strip()

    name = re.sub(r'^(?:quote|tender|offer|rfq|vendor_quote|vendor|dummy)[-_ ]+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[-_ ]+(?:quote|quotation|tender|offer|rfq|demo|rev\d*|v\d*)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[\s_\-]*(?:\(\d+\)|v\d+|\d{2,})+$', '', name, flags=re.IGNORECASE)

    legal_suffixes = [
        r'\(pty\)\s*ltd\.?', r'pty\s*ltd\.?', r'\(pty\)', r'\(proprietary\)\s*limited',
        r'limited', r'ltd\.?', r'inc\.?', r'llc', r'co\.', r'corporation',
        r'commercial\s*systems', r'air\s*systems', r'applied\s*solutions', r'commercial\s*hvac\s*solutions'
    ]
    for ls in legal_suffixes:
        name = re.sub(r'[\s,]+' + ls + r'\s*$', '', name, flags=re.IGNORECASE)

    name = re.sub(r'[-_.]+', ' ', name).strip()

    words = name.split()
    formatted_words = []
    for w in words:
        if w.isupper() and len(w) > 4:
            formatted_words.append(w.capitalize())
        elif w.islower():
            formatted_words.append(w.capitalize())
        else:
            formatted_words.append(w)
            
    base_name = " ".join(formatted_words[:3]) if len(formatted_words) > 3 else " ".join(formatted_words)
    if not base_name:
        base_name = str(raw)[:25].strip()

    full_label = f"{base_name}{tier_suffix}".strip()
    return full_label[:40].strip()


