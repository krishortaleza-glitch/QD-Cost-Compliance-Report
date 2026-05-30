import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="QD Compliance Checker",
    layout="wide"
)

st.title("QD Compliance Checker")

st.write("Upload the required files below.")

cost_file = st.file_uploader(
    "QD Cost File",
    type=["csv"]
)

invoice_file = st.file_uploader(
    "Invoice File",
    type=["csv"]
)

promotion_file = st.file_uploader(
    "Promotion File",
    type=["csv"]
)

vendor_file = st.file_uploader(
    "Vendor Mapping File",
    type=["csv"]
)

if (
    cost_file
    and invoice_file
    and promotion_file
    and vendor_file
):
    st.success("All files uploaded successfully!")

    cost_df = pd.read_csv(cost_file)
    invoice_df = pd.read_csv(invoice_file)
    promotion_df = pd.read_csv(promotion_file)
    vendor_df = pd.read_csv(vendor_file)

    st.subheader("QD Cost File")
    st.dataframe(cost_df.head())

    st.subheader("Invoice File")
    st.dataframe(invoice_df.head())

    st.subheader("Promotion File")
    st.dataframe(promotion_df.head())

    st.subheader("Vendor Mapping File")
    st.dataframe(vendor_df.head())
