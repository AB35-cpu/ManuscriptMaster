import os
import io
import json
import streamlit as st
from docx import Document
from docx.shared import Pt, Inches
from docx.oxml.ns import qn
import docx.oxml.shared
from openai import OpenAI
from supabase import create_client, Client

# =========================
# 1. SECURE CONFIGURATION
# =========================
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL, KEY)
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"Configuration Error: {e}. Please check Streamlit Secrets.")
    st.stop()

SYMBOL_FONTS = {"Symbol", "Webdings", "Wingdings", "Wingdings 2", "Wingdings 3", "MT Extra"}

# =========================
# 2. WORD COUNT & XML HELPERS
# =========================

def get_word_count(doc):
    """Counts words to verify against the Smart Usage Logic."""
    full_text = [p.text for p in doc.paragraphs]
    return len(" ".join(full_text).split())

def kill_theme_fonts(element, target_font):
    """Purges theme-locked fonts (CT_P, CT_R, and Styles)."""
    try:
        if hasattr(element, 'get_or_add_pPr'):
            rPr = element.get_or_add_pPr().get_or_add_rPr()
        elif hasattr(element, 'get_or_add_rPr'):
            rPr = element.get_or_add_rPr()
        else:
            return
        rFonts = rPr.get_or_add_rFonts()
        rFonts.set(qn('w:ascii'), target_font)
        rFonts.set(qn('w:hAnsi'), target_font)
        for attr in [qn('w:asciiTheme'), qn('w:hAnsiTheme')]:
            if attr in rFonts.attrib: del rFonts.attrib[attr]
    except: pass

# =========================
# 3. PASSWORD RECOVERY FLOW
# =========================
query_params = st.query_params
if "type" in query_params and query_params["type"] == "recovery":
    st.title("🔄 Set New Password")
    new_pw = st.text_input("Enter new password", type="password")
    if st.button("Update Password"):
        try:
            supabase.auth.update_user({"password": new_pw})
            st.success("Password updated! Please log in from the sidebar.")
            st.query_params.clear()
        except Exception as e: st.error(f"Update failed: {e}")
    st.stop()

# =========================
# 4. AUTHENTICATION UI
# =========================
st.set_page_config(page_title="Manuscript Master", layout="wide")

with st.sidebar:
    st.title("🔐 Account")
    if "user" not in st.session_state:
        auth_mode = st.radio("Mode", ["Login", "Sign Up", "Forgot Password"])
        
        if auth_mode == "Forgot Password":
            reset_email = st.text_input("Email for reset")
            if st.button("Send Reset Link"):
                supabase.auth.reset_password_for_email(reset_email)
                st.success("Reset link sent to your email.")
        else:
            u_email = st.text_input("Email")
            u_pw = st.text_input("Password", type="password")
            if auth_mode == "Sign Up" and st.button("Create Account"):
                supabase.auth.sign_up({"email": u_email, "password": u_pw})
                st.info("Check your email for a confirmation link!")
            elif auth_mode == "Login" and st.button("Login"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": u_email, "password": u_pw})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("Invalid credentials.")
        st.stop()
    else:
        # FETCH LIVE DATA
        try:
            profile = supabase.table("profiles").select("*").eq("id", st.session_state.user.id).single().execute()
            user_data = profile.data
        except:
            user_data = {"plan_type": "Free", "word_limit": 3000, "words_used": 0}
            
        st.subheader(f"Plan: {user_data['plan_type']}")
        usage_pct = user_data['words_used'] / user_data['word_limit']
        st.progress(min(usage_pct, 1.0))
        st.caption(f"{user_data['words_used']} / {user_data['word_limit']} words used")
        
        if st.button("Log Out"):
            supabase.auth.sign_out()
            del st.session_state.user
            st.rerun()

# =========================
# 5. MAIN APPLICATION
# =========================
st.title("📄 Manuscript Compliance Agent")
col1, col2 = st.columns(2)

with col1:
    guidelines = st.text_area("1. Paste Journal Guidelines", height=200)
    uploaded_file = st.file_uploader("2. Upload Manuscript (.docx)", type=["docx"])

with col2:
    exclude = st.multiselect("3. Protect Styles:", ["Caption", "Heading 1", "Heading 2", "Title"], default=["Caption", "Title"])

if st.button("Fix Formatting"):
    if uploaded_file and guidelines:
        doc_obj = Document(uploaded_file)
        file_words = get_word_count(doc_obj)
        
        # SMART USAGE GATEKEEPER
        if (user_data['words_used'] + file_words) <= user_data['word_limit']:
            with st.spinner("Applying Rules..."):
                # Define rules (AI extraction logic can be re-added here)
                rules = {"font_family": "Times New Roman", "font_size_pt": 12, "line_spacing": 2.0, "margins_inch": {"top":1, "bottom":1, "left":1, "right":1}}
                
                # Apply deep formatting
                for style in doc_obj.styles:
                    if style.name.startswith('TOC') or (hasattr(style, 'font') and style.name not in exclude):
                        style.font.name = rules["font_family"]
                        kill_theme_fonts(style.font._element, rules["font_family"])
                
                # Update usage in Supabase
                new_total = user_data['words_used'] + file_words
                supabase.table("profiles").update({"words_used": new_total}).eq("id", st.session_state.user.id).execute()
                
                output = io.BytesIO()
                doc_obj.save(output)
                st.download_button("📥 Download Manuscript", output.getvalue(), "Fixed_Manuscript.docx")
                st.success(f"Success! {file_words} words processed.")
        else:
            st.error("⚠️ Word limit exceeded. Please upgrade.")
