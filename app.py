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
# SECURE CONFIGURATION
# =========================
try:
    # Connect to Supabase
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL, KEY)
    
    # Connect to OpenAI
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    st.error(f"Missing Secrets: {e}")
    st.stop()

# =========================
# SMART USAGE HELPERS
# =========================

def get_word_count(doc):
    """Accurately count words in the uploaded manuscript."""
    full_text = [p.text for p in doc.paragraphs]
    return len(" ".join(full_text).split())

def kill_theme_fonts(element, target_font):
    """Universally handles XML for Paragraphs (CT_P), Runs (CT_R), and Styles."""
    try:
        # Paragraphs (CT_P) use pPr -> rPr
        if hasattr(element, 'get_or_add_pPr'):
            pPr = element.get_or_add_pPr()
            rPr = pPr.get_or_add_rPr()
        # Runs and Styles use rPr directly
        elif hasattr(element, 'get_or_add_rPr'):
            rPr = element.get_or_add_rPr()
        else:
            return

        rFonts = rPr.get_or_add_rFonts()
        rFonts.set(qn('w:ascii'), target_font)
        rFonts.set(qn('w:hAnsi'), target_font)
        
        # Purge theme attributes
        for attr in [qn('w:asciiTheme'), qn('w:hAnsiTheme')]:
            if attr in rFonts.attrib:
                del rFonts.attrib[attr]
    except:
        pass

# =========================
# MAIN APP INTERFACE
# =========================
st.set_page_config(page_title="Manuscript Master", layout="wide")

# --- AUTHENTICATION UI IN SIDEBAR ---
with st.sidebar:
    st.title("🔐 Account")
    if "user" not in st.session_state:
        auth_mode = st.radio("Choose Mode", ["Login", "Sign Up"])
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        if auth_mode == "Sign Up":
            if st.button("Create Account"):
                try:
                    res = supabase.auth.sign_up({"email": email, "password": password})
                    st.success("Check your email for a verification link!")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            if st.button("Login"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    st.rerun() # Refresh to show the app
                except Exception as e:
                    st.error("Invalid email or password.")
        st.stop() # Stops the rest of the app from loading until login
    else:
        if st.button("Log Out"):
            supabase.auth.sign_out()
            del st.session_state.user
            st.rerun()

user = st.session_state.user
# Fetch live data from Supabase Profiles
profile = supabase.table("profiles").select("*").eq("id", user.id).single().execute()
user_data = profile.data

# Sidebar Usage Tracking
st.sidebar.title("💎 Usage Status")
st.sidebar.write(f"Plan: **{user_data['plan_type']}**")
usage_percent = user_data['words_used'] / user_data['word_limit']
st.sidebar.progress(min(usage_percent, 1.0))
st.sidebar.caption(f"{user_data['words_used']} / {user_data['word_limit']} words used")

# Formatting UI
st.title("📄 Manuscript Compliance Agent")
uploaded_file = st.file_uploader("Upload Manuscript (.docx)", type=["docx"])
guidelines = st.text_area("Paste Journal Guidelines")

if st.button("Purge Theme Fonts & Fix Formatting"):
    if uploaded_file and guidelines:
        doc_obj = Document(uploaded_file)
        file_words = get_word_count(doc_obj)
        
        # SMART USAGE LOGIC: Check before processing
        if (user_data['words_used'] + file_words) <= user_data['word_limit']:
            with st.spinner("Processing AI Formatting..."):
                # (Your AI rules extraction and apply_deep_formatting logic goes here)
                
                # Update Database after success
                new_total = user_data['words_used'] + file_words
                supabase.table("profiles").update({"words_used": new_total}).eq("id", user.id).execute()
                
                st.success(f"Success! {file_words} words added to your usage.")
        else:
            st.error(f"⚠️ Limit Exceeded! This file is {file_words} words, but you only have {user_data['word_limit'] - user_data['words_used']} left.")
            st.button("💎 Upgrade to Basic ($9)")

