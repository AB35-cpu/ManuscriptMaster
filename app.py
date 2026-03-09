import os
import io
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
    # Essential for connecting your app to the database and AI
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL, KEY)
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"Configuration Error: {e}. Check Streamlit Secrets.")
    st.stop()

# =========================
# 2. RECOVERY INTERCEPTOR
# =========================
# This must run at the very top to catch password reset links
query_params = st.query_params
if "type" in query_params and query_params["type"] == "recovery":
    st.title("🔄 Reset Your Password")
    with st.form("recovery_form"):
        new_pw = st.text_input("New Password", type="password")
        confirm_pw = st.text_input("Confirm Password", type="password")
        if st.form_submit_button("Update Password"):
            if new_pw == confirm_pw and len(new_pw) >= 6:
                try:
                    supabase.auth.update_user({"password": new_pw})
                    st.success("✅ Password updated! You can now log in.")
                    st.query_params.clear()
                except Exception as e: st.error(f"Update failed: {e}")
            else: st.error("Passwords must match and be 6+ characters.")
    st.stop()

# =========================
# 3. HELPERS: XML & WORD COUNT
# =========================

def get_word_count(doc):
    """Calculates usage against the 3,000-word Free Plan limit."""
    return len(" ".join([p.text for p in doc.paragraphs]).split())

def kill_theme_fonts(element, target_font):
    """Fixes 'CT_P' and 'CT_Style' errors by purging Calibri themes."""
    try:
        if hasattr(element, 'get_or_add_pPr'):
            rPr = element.get_or_add_pPr().get_or_add_rPr()
        elif hasattr(element, 'get_or_add_rPr'):
            rPr = element.get_or_add_rPr()
        else: return
        rFonts = rPr.get_or_add_rFonts()
        rFonts.set(qn('w:ascii'), target_font)
        rFonts.set(qn('w:hAnsi'), target_font)
        for attr in [qn('w:asciiTheme'), qn('w:hAnsiTheme')]:
            if attr in rFonts.attrib: del rFonts.attrib[attr]
    except: pass

# =========================
# 4. SIDEBAR: AUTH & USAGE
# =========================
st.set_page_config(page_title="Manuscript Master", layout="wide")

with st.sidebar:
    st.title("🔐 Account")
    if "user" not in st.session_state:
        auth_mode = st.radio("Mode", ["Login", "Sign Up", "Forgot Password"])
        u_email = st.text_input("Email")
        
        if auth_mode == "Forgot Password":
            if st.button("Send Reset Link"):
                supabase.auth.reset_password_for_email(u_email)
                st.success("Reset link sent!")
        else:
            u_pw = st.text_input("Password", type="password")
            if auth_mode == "Sign Up" and st.button("Create Account"):
                if len(u_pw) < 6: st.error("Min 6 characters.")
                else:
                    try:
                        supabase.auth.sign_up({"email": u_email, "password": u_pw})
                        st.success("Account created! Verify email if enabled.")
                    except Exception as e: st.error(f"Error: {e}")
            elif auth_mode == "Login" and st.button("Login"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": u_email, "password": u_pw})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("Invalid login.")
        st.stop()
    else:
        # Fetching profile for Smart Usage Logic
        try:
            profile = supabase.table("profiles").select("*").eq("id", st.session_state.user.id).single().execute()
            user_data = profile.data
        except:
            user_data = {"plan_type": "Free", "word_limit": 3000, "words_used": 0}
        
        st.subheader(f"Plan: {user_data['plan_type']}")
        usage_pct = user_data['words_used'] / user_data['word_limit']
        st.progress(min(usage_pct, 1.0))
        st.caption(f"{user_data['words_used']} / {user_data['word_limit']} words")
        if st.button("Log Out"):
            supabase.auth.sign_out()
            del st.session_state.user
            st.rerun()

# =========================
# 5. MAIN APP
# =========================
st.title("📄 Manuscript Compliance Agent")
col1, col2 = st.columns(2)

with col1:
    guidelines = st.text_area("1. Paste Journal Guidelines", height=200)
    uploaded_file = st.file_uploader("2. Upload Manuscript (.docx)", type=["docx"])

with col2:
    exclude = st.multiselect("3. Protect Styles:", ["Caption", "Heading 1", "Title"], default=["Caption", "Title"])

if st.button("Fix Formatting"):
    if uploaded_file and guidelines:
        doc = Document(uploaded_file)
        file_words = get_word_count(doc)
        
        # GATEKEEPER: Check word limit
        if (user_data['words_used'] + file_words) <= user_data['word_limit']:
            with st.spinner("Processing..."):
                # Demo Rule (Replacement for AI logic)
                font = "Times New Roman"
                for style in doc.styles:
                    if hasattr(style, 'font') and style.name not in exclude:
                        style.font.name = font
                        kill_theme_fonts(style.font._element, font)
                
                # Update database usage
                new_total = user_data['words_used'] + file_words
                supabase.table("profiles").update({"words_used": new_total}).eq("id", st.session_state.user.id).execute()
                
                output = io.BytesIO()
                doc.save(output)
                st.download_button("📥 Download Manuscript", output.getvalue(), "Formatted.docx")
                st.success(f"Processed {file_words} words!")
        else:
            st.error(f"Limit Exceeded! This file is {file_words} words, but you only have {user_data['word_limit'] - user_data['words_used']} left.")
