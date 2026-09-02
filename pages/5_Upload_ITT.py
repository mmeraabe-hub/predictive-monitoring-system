
import streamlit as st
st.set_page_config(
    page_title="Upload Existing ITT",
    page_icon="📤",
    layout="wide"
)
st.title("Upload Existing ITT")
uploaded_file = st.file_uploader(
    "Upload an Excel ITT",
    type=["xlsx"]
)
if uploaded_file is not None:
    st.success(
        "The file was received. Validation and transformation "
        "will be added in the next build."
)
