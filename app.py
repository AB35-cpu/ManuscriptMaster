from supabase import create_client, Client

# --- DB CONNECTION ---
# These must be in your Streamlit Secrets!
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# --- USER AUTHENTICATION UI ---
st.sidebar.title("🔐 Account")
menu = ["Login", "Sign Up"]
choice = st.sidebar.selectbox("Action", menu)

user = None

if choice == "Sign Up":
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Create Account"):
        res = supabase.auth.sign_up({"email": email, "password": password})
        st.sidebar.success("Check your email for a confirmation link!")

elif choice == "Login":
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.sidebar.success(f"Logged in as {res.user.email}")
        except Exception as e:
            st.sidebar.error("Invalid login credentials")

# Check if user is logged in
if "user" in st.session_state and st.session_state.user:
    user = st.session_state.user
    
    # FETCH PROFILE DATA (Word usage, Plan Type)
    profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute()
    user_data = profile.data

    # --- SIDEBAR USAGE DASHBOARD ---
    st.sidebar.divider()
    st.sidebar.subheader(f"Plan: {user_data['plan_type']}")
    
    # Usage Progress Bar
    usage_percent = user_data['words_used'] / user_data['word_limit']
    st.sidebar.progress(min(usage_percent, 1.0))
    st.sidebar.write(f"Used: {user_data['words_used']} / {user_data['word_limit']} words")

    # SHOW UPGRADE BUTTON IF NEAR LIMIT
    if usage_percent >= 0.9:
        st.sidebar.warning("You are almost at your limit!")
        # (Step 3 will link this to Lemon Squeezy)
        st.sidebar.button("💎 Upgrade Now")

import os
import json
import io
import streamlit as st
from docx import Document
from docx.shared import Pt, Inches
from docx.oxml.ns import qn
import docx.oxml.shared
from openai import OpenAI

# =========================
# SECURE CONFIGURATION
# =========================
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception:
    st.error("OpenAI API Key not found in Secrets!")

SYMBOL_FONTS = {"Symbol", "Webdings", "Wingdings", "Wingdings 2", "Wingdings 3", "MT Extra"}

# =========================
# HELPER FUNCTIONS
# =========================

def get_word_count(doc):
    """Accurately counts words to estimate pages (300 words = 1 page)."""
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    words = " ".join(full_text).split()
    return len(words)

def kill_theme_fonts(element, target_font):
    try:
        if hasattr(element, 'get_or_add_pPr'):
            pPr = element.get_or_add_pPr()
            rPr = pPr.get_or_add_rPr()
        elif hasattr(element, 'get_or_add_rPr'):
            rPr = element.get_or_add_rPr()
        else:
            rPr = element.find(qn('w:rPr'))
            if rPr is None:
                rPr = docx.oxml.shared.OxmlElement('w:rPr')
                element.append(rPr)
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = docx.oxml.shared.OxmlElement('w:rFonts')
            rPr.append(rFonts)
        rFonts.set(qn('w:ascii'), target_font)
        rFonts.set(qn('w:hAnsi'), target_font)
        rFonts.set(qn('w:eastAsia'), target_font)
        rFonts.set(qn('w:cs'), target_font)
        themes = [qn('w:asciiTheme'), qn('w:hAnsiTheme'), qn('w:eastAsiaTheme'), qn('w:cstheme')]
        for attr in themes:
            if attr in rFonts.attrib:
                del rFonts.attrib[attr]
    except Exception:
        pass

# =========================
# CORE FORMATTING ENGINE
# =========================

def apply_deep_formatting(doc, rules, skip_styles):
    target_font = rules.get("font_family")
    target_size = rules.get("font_size_pt")
    if target_font:
        for style in doc.styles:
            is_toc = style.name.startswith('TOC')
            if (hasattr(style, 'font') and style.name not in skip_styles) or is_toc:
                try:
                    style.font.name = target_font
                    kill_theme_fonts(style.font._element, target_font)
                    if target_size: style.font.size = Pt(target_size)
                except: continue
    if rules.get("margins_inch"):
        m = rules["margins_inch"]
        for section in doc.sections:
            section.top_margin, section.bottom_margin = Inches(m["top"]), Inches(m["bottom"])
            section.left_margin, section.right_margin = Inches(m["left"]), Inches(m["right"])

    def process_container(container):
        for para in container.paragraphs:
            if para.style and para.style.name in skip_styles: continue
            if target_font: kill_theme_fonts(para._element, target_font)
            if rules.get("line_spacing"): para.paragraph_format.line_spacing = rules["line_spacing"]
            for run in para.runs:
                if run.font.name in SYMBOL_FONTS or 'OMath' in run._element.xml: continue
                if target_font: kill_theme_fonts(run._element, target_font)
                if target_size: run.font.size = Pt(target_size)

    process_container(doc)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells: process_container(cell)
    return doc

# =========================
# STREAMLIT UI
# =========================
st.set_page_config(page_title="Manuscript Pro", layout="wide")

# --- SIDEBAR PRICING ---
with st.sidebar:
    st.title("💎 Membership")
    st.info("**Current Plan:** Free Tier")
    st.progress(0.4) # Mock 4/10 pages used
    st.caption("4 of 10 free weekly pages used.")
    
    st.divider()
    st.subheader("Upgrade to Pro")
    st.markdown("""
    * **Unlimited** pages/week
    * **Bulk upload** (up to 5 files)
    * **Priority** processing
    * **No ads** on reports
    """)
    if st.button("🚀 Upgrade for $19/mo"):
        st.write("Redirecting to Stripe...")

# --- MAIN APP ---
st.title("📄 Manuscript Compliance Agent")

if "fixed_docx" not in st.session_state:
    st.session_state.fixed_docx = None

col1, col2 = st.columns([1, 1])

with col1:
    guidelines_text = st.text_area("1. Paste Journal Guidelines", height=150)
    uploaded_file = st.file_uploader("2. Upload Manuscript (.docx)", type=["docx"])

with col2:
    exclude_list = st.multiselect(
        "3. Protect Styles:",
        ["Caption", "Heading 1", "Heading 2", "Heading 3", "Title"],
        default=["Caption", "Title"]
    )

if st.button("Fix Formatting"):
    if guidelines_text and uploaded_file:
        doc_obj = Document(uploaded_file)
        
        # Word Count / Page Estimation
        words = get_word_count(doc_obj)
        est_pages = max(1, words // 300)
        
        if est_pages > 10:
            st.error(f"⚠️ This manuscript is ~{est_pages} pages. Your free limit is 10 pages.")
            st.button("Pay $2.00 to process this file")
        else:
            with st.spinner("Processing deep XML purge..."):
                rules = {"font_family": "Times New Roman", "font_size_pt": 12, "line_spacing": 2.0, "margins_inch": {"top":1, "bottom":1, "left":1, "right":1}} # Logic for demo
                fixed_doc = apply_deep_formatting(doc_obj, rules, exclude_list)
                doc_io = io.BytesIO()
                fixed_doc.save(doc_io)
                st.session_state.fixed_docx = doc_io.getvalue()
                st.success(f"Success! Estimated {est_pages} pages used from your weekly quota.")

if st.session_state.fixed_docx:

    st.download_button("📥 Download Fixed Manuscript", st.session_state.fixed_docx, "Fixed_Manuscript.docx")
