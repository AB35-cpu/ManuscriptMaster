import os
import io
import streamlit as st
from docx import Document
from docx.oxml.ns import qn
from openai import OpenAI
from supabase import create_client, Client

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="Manuscript Master", layout="wide")

# =========================
# 1. SECURE CONFIGURATION
# =========================
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    OPENAI_KEY = st.secrets["OPENAI_API_KEY"]

    supabase: Client = create_client(URL, KEY)
    client = OpenAI(api_key=OPENAI_KEY)

except Exception as e:
    st.error(f"Secrets configuration error: {e}")
    st.stop()

# =========================
# 2. PASSWORD RECOVERY HANDLER
# =========================

query_params = st.query_params

if query_params.get("type") == "recovery":

    st.title("🔑 Reset Your Password")

    with st.form("reset_form"):

        new_pw = st.text_input("New Password", type="password")
        confirm_pw = st.text_input("Confirm Password", type="password")

        submitted = st.form_submit_button("Update Password")

        if submitted:

            if new_pw != confirm_pw:
                st.error("Passwords do not match.")
                st.stop()

            if len(new_pw) < 6:
                st.error("Password must be at least 6 characters.")
                st.stop()

            try:
                supabase.auth.update_user(
                    {"password": new_pw}
                )

                st.success("Password updated successfully.")
                st.info("You can now login.")

                st.query_params.clear()

            except Exception as e:
                st.error(f"Password reset failed: {e}")

    st.stop()

# =========================
# 3. WORD COUNT
# =========================

def get_word_count(doc):
    return len(" ".join([p.text for p in doc.paragraphs]).split())

# =========================
# 4. FONT FIX
# =========================

def kill_theme_fonts(element, target_font):

    try:

        if hasattr(element, "get_or_add_rPr"):
            rPr = element.get_or_add_rPr()
        else:
            return

        rFonts = rPr.get_or_add_rFonts()

        rFonts.set(qn("w:ascii"), target_font)
        rFonts.set(qn("w:hAnsi"), target_font)

        if qn("w:asciiTheme") in rFonts.attrib:
            del rFonts.attrib[qn("w:asciiTheme")]

        if qn("w:hAnsiTheme") in rFonts.attrib:
            del rFonts.attrib[qn("w:hAnsiTheme")]

    except:
        pass

# =========================
# 5. SIDEBAR AUTH
# =========================

with st.sidebar:

    st.title("🔐 Account")

    if "user" not in st.session_state:

        mode = st.radio(
            "Select",
            ["Login", "Sign Up", "Forgot Password"]
        )

        email = st.text_input("Email")

        if mode == "Forgot Password":

            if st.button("Send Reset Email"):

                try:

                    supabase.auth.reset_password_for_email(
                        email,
                        {
                            "redirect_to": st.experimental_get_query_params()
                        }
                    )

                    st.success("Password reset email sent.")

                except Exception as e:
                    st.error(e)

        else:

            password = st.text_input("Password", type="password")

            if mode == "Sign Up":

                if st.button("Create Account"):

                    try:

                        supabase.auth.sign_up(
                            {
                                "email": email,
                                "password": password
                            }
                        )

                        st.success("Account created successfully.")

                    except Exception as e:
                        st.error(e)

            if mode == "Login":

                if st.button("Login"):

                    try:

                        res = supabase.auth.sign_in_with_password(
                            {
                                "email": email,
                                "password": password
                            }
                        )

                        st.session_state.user = res.user

                        st.rerun()

                    except Exception:
                        st.error("Invalid login credentials")

        st.stop()

    else:

        st.success(f"Logged in")

        if st.button("Logout"):

            supabase.auth.sign_out()

            del st.session_state.user

            st.rerun()

# =========================
# 6. MAIN APP
# =========================

st.title("📄 Manuscript Compliance Agent")

col1, col2 = st.columns(2)

with col1:

    guidelines = st.text_area(
        "1. Paste Journal Guidelines",
        height=200
    )

    uploaded_file = st.file_uploader(
        "2. Upload Manuscript (.docx)",
        type=["docx"]
    )

with col2:

    exclude = st.multiselect(
        "3. Protect Styles",
        ["Caption", "Heading 1", "Title"],
        default=["Caption", "Title"]
    )

if st.button("Fix Formatting"):

    if not uploaded_file or not guidelines:

        st.warning("Upload manuscript and guidelines first.")
        st.stop()

    doc = Document(uploaded_file)

    font = "Times New Roman"

    for style in doc.styles:

        if hasattr(style, "font") and style.name not in exclude:

            style.font.name = font

            kill_theme_fonts(style.font._element, font)

    output = io.BytesIO()

    doc.save(output)

    st.download_button(
        "Download Formatted Manuscript",
        output.getvalue(),
        file_name="formatted_manuscript.docx"
    )

    st.success("Formatting fixed successfully.")
