
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="QD Cost Compliance Report", layout="wide")

def clean_id(series):
    return (
        series.astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
    )

@st.cache_data
def load_csv(file):
    return pd.read_csv(file)

def prepare_data(cost_df, invoice_df):
    cost_df = cost_df.copy()
    invoice_df = invoice_df.copy()

    cost_df["StoreID"] = clean_id(cost_df["StoreID"])
    cost_df["ProductUID"] = clean_id(cost_df["retailProductUID"])

    invoice_df["StoreID"] = clean_id(invoice_df["store"])
    invoice_df["ProductUID"] = clean_id(invoice_df["productId"])

    cost_df["date"] = pd.to_datetime(cost_df["date"], errors="coerce")
    cost_df["endDate"] = pd.to_datetime(cost_df["endDate"], errors="coerce")
    invoice_df["date"] = pd.to_datetime(invoice_df["date"], errors="coerce")

    for c in ["caseCost"]:
        cost_df[c] = pd.to_numeric(cost_df[c], errors="coerce")

    for c in ["price", "quantity"]:
        invoice_df[c] = pd.to_numeric(invoice_df[c], errors="coerce")

    return cost_df, invoice_df

def build_compliance_report(cost_df, invoice_df):
    results = []
    evidence = []

    for _, row in cost_df.iterrows():
        invoices = invoice_df[
            (invoice_df["StoreID"] == row["StoreID"]) &
            (invoice_df["ProductUID"] == row["ProductUID"]) &
            (invoice_df["date"] >= row["date"]) &
            (invoice_df["date"] <= row["endDate"])
        ]

        if len(invoices) == 0:
            status = "NO INVOICE"
            lowest = np.nan
            variance = np.nan
            qty = 0
            overage = 0
        else:
            lowest = invoices["price"].min()
            variance = lowest - row["caseCost"]
            qty = invoices["quantity"].sum()
            overage = ((invoices["price"] - row["caseCost"]) * invoices["quantity"]).sum()
            status = "PASS" if lowest >= row["caseCost"] else "FAIL"

            temp = invoices.copy()
            temp["ExpectedCost"] = row["caseCost"]
            temp["Status"] = status
            temp["RetailProductName"] = row["retailProductName"]
            evidence.append(temp)

        results.append({
            "StoreID": row["StoreID"],
            "Vendor": row["vendorName"],
            "ProductUID": row["ProductUID"],
            "ProductName": row["retailProductName"],
            "ProductType": row["category"],
            "Family": row["family"],
            "PackageGroup": row["group"],
            "ExpectedCost": row["caseCost"],
            "LowestActualCost": lowest,
            "Variance": variance,
            "TotalCases": qty,
            "OverageDollars": round(overage, 2),
            "Status": status,
            "StartDate": row["date"],
            "EndDate": row["endDate"]
        })

    evidence_df = pd.concat(evidence, ignore_index=True) if evidence else pd.DataFrame()
    return pd.DataFrame(results), evidence_df

def to_excel(summary_df, fail_df, pass_df, store_df, vendor_df, product_df, evidence_df, exception_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        fail_df.to_excel(writer, sheet_name="Failures", index=False)
        pass_df.to_excel(writer, sheet_name="Pass", index=False)
        store_df.to_excel(writer, sheet_name="Store Summary", index=False)
        vendor_df.to_excel(writer, sheet_name="Vendor Summary", index=False)
        product_df.to_excel(writer, sheet_name="Product Type Summary", index=False)
        evidence_df.to_excel(writer, sheet_name="Invoice Evidence", index=False)
        exception_df.to_excel(writer, sheet_name="Exceptions", index=False)
    return output.getvalue()

st.title("QD Cost Compliance Report")

cost_file = st.file_uploader("QD Cost File", type=["csv"])
invoice_file = st.file_uploader("Invoice File", type=["csv"])

if cost_file and invoice_file:
    cost_df = load_csv(cost_file)
    invoice_df = load_csv(invoice_file)

    cost_df, invoice_df = prepare_data(cost_df, invoice_df)

    compliance_df, evidence_df = build_compliance_report(cost_df, invoice_df)

    pass_df = compliance_df[compliance_df["Status"] == "PASS"]
    fail_df = compliance_df[compliance_df["Status"] == "FAIL"]
    exception_df = compliance_df[compliance_df["Status"] == "NO INVOICE"]

    total = len(compliance_df)
    passed = len(pass_df)
    failed = len(fail_df)
    noinv = len(exception_df)

    comp_pct = round((passed / (passed + failed) * 100), 2) if (passed + failed) else 0

    total_overage = round(compliance_df["OverageDollars"].sum(), 2)
    total_cases = int(compliance_df["TotalCases"].sum())

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Products", total)
    c2.metric("Pass", passed)
    c3.metric("Fail", failed)
    c4.metric("No Invoice", noinv)
    c5.metric("Compliance %", f"{comp_pct}%")
    c6.metric("Overage $", f"${total_overage:,.2f}")
    st.metric("Total Cases", f"{total_cases:,}")

    store_df = compliance_df.groupby("StoreID").agg(
        Products=("ProductUID","count"),
        Pass=("Status", lambda x:(x=="PASS").sum()),
        Fail=("Status", lambda x:(x=="FAIL").sum()),
        NoInvoice=("Status", lambda x:(x=="NO INVOICE").sum()),
        OverageDollars=("OverageDollars","sum")
    ).reset_index()

    store_df["Compliance%"] = np.where(
        (store_df["Pass"]+store_df["Fail"])>0,
        round(store_df["Pass"]/(store_df["Pass"]+store_df["Fail"])*100,2),
        0
    )

    vendor_df = compliance_df.groupby("Vendor").agg(
        Products=("ProductUID","count"),
        Pass=("Status", lambda x:(x=="PASS").sum()),
        Fail=("Status", lambda x:(x=="FAIL").sum()),
        OverageDollars=("OverageDollars","sum")
    ).reset_index()

    vendor_df["Compliance%"] = np.where(
        (vendor_df["Pass"]+vendor_df["Fail"])>0,
        round(vendor_df["Pass"]/(vendor_df["Pass"]+vendor_df["Fail"])*100,2),
        0
    )

    product_df = compliance_df.groupby(
        ["ProductType","Family","PackageGroup"]
    ).agg(
        Products=("ProductUID","count"),
        Stores=("StoreID","nunique"),
        Cases=("TotalCases","sum"),
        OverageDollars=("OverageDollars","sum"),
        Pass=("Status", lambda x:(x=="PASS").sum()),
        Fail=("Status", lambda x:(x=="FAIL").sum())
    ).reset_index()

    product_df["Compliance%"] = np.where(
        (product_df["Pass"]+product_df["Fail"])>0,
        round(product_df["Pass"]/(product_df["Pass"]+product_df["Fail"])*100,2),
        0
    )

    tabs = st.tabs([
        "Failures","Pass","Store Summary","Vendor Summary",
        "Product Type Summary","Invoice Evidence","Exceptions","All Results"
    ])

    with tabs[0]:
        st.dataframe(fail_df, use_container_width=True)

    with tabs[1]:
        st.dataframe(pass_df, use_container_width=True)

    with tabs[2]:
        st.dataframe(store_df, use_container_width=True)

    with tabs[3]:
        st.dataframe(vendor_df, use_container_width=True)

    with tabs[4]:
        st.dataframe(product_df, use_container_width=True)

    with tabs[5]:
        st.dataframe(evidence_df, use_container_width=True)

    with tabs[6]:
        st.dataframe(exception_df, use_container_width=True)

    with tabs[7]:
        st.dataframe(compliance_df, use_container_width=True)

    summary_df = pd.DataFrame({
        "Metric":["Products","Pass","Fail","No Invoice","Compliance %","Overage $","Total Cases"],
        "Value":[total,passed,failed,noinv,comp_pct,total_overage,total_cases]
    })

    excel_file = to_excel(
        summary_df, fail_df, pass_df,
        store_df, vendor_df, product_df,
        evidence_df, exception_df
    )

    st.download_button(
        "Download Excel Report",
        excel_file,
        "QD_Cost_Compliance_Report.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
