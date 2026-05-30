import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="QD Compliance Checker",
    layout="wide"
)

# =====================================================
# HELPERS
# =====================================================

def clean_id(series):
    return (
        series.astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
        .str.lstrip("0")
    )


@st.cache_data
def load_csv(uploaded_file):
    return pd.read_csv(uploaded_file)


def prepare_data(cost_df, invoice_df, promotion_df, vendor_df):

    cost_df = cost_df.copy()
    invoice_df = invoice_df.copy()
    promotion_df = promotion_df.copy()
    vendor_df = vendor_df.copy()

    # Cost File

    cost_df["ProductUID"] = clean_id(cost_df["retailProductUID"])
    cost_df["VendorUID"] = clean_id(cost_df["vendorProductUID"])
    cost_df["StoreID"] = clean_id(cost_df["StoreID"])

    # Invoice File

    invoice_df["ProductUID"] = clean_id(invoice_df["productId"])
    invoice_df["StoreID"] = clean_id(invoice_df["store"])
    invoice_df["Alias"] = clean_id(invoice_df["alias"])

    # Promotion File

    promotion_df["ProductUID"] = clean_id(promotion_df["ProductUID"])
    promotion_df["VendorUID"] = clean_id(promotion_df["VendorUID"])

    # Vendor File

    vendor_df["StoreID"] = clean_id(vendor_df["store"])
    vendor_df["Alias"] = clean_id(vendor_df["vendorAlias"])

    # Dates

    cost_df["date"] = pd.to_datetime(
        cost_df["date"],
        errors="coerce"
    )

    cost_df["endDate"] = pd.to_datetime(
        cost_df["endDate"],
        errors="coerce"
    )

    invoice_df["date"] = pd.to_datetime(
        invoice_df["date"],
        errors="coerce"
    )

    return cost_df, invoice_df, promotion_df, vendor_df


def build_compliance_report(
    cost_df,
    invoice_df,
    promotion_df,
    vendor_df
):

    # ==========================================
    # Attach Vendor Name to Invoice
    # ==========================================

    invoice_df = invoice_df.merge(
        vendor_df[
            [
                "StoreID",
                "Alias",
                "vendorName"
            ]
        ].drop_duplicates(),
        on=[
            "StoreID",
            "Alias"
        ],
        how="left"
    )

    # ==========================================
    # Product + VendorName -> VendorUID
    # ==========================================

    vendor_lookup = (
        cost_df[
            [
                "ProductUID",
                "vendorName",
                "VendorUID"
            ]
        ]
        .drop_duplicates()
    )

    invoice_df = invoice_df.merge(
        vendor_lookup,
        on=[
            "ProductUID",
            "vendorName"
        ],
        how="left"
    )

    # ==========================================
    # Product + VendorUID -> MixMatchID
    # ==========================================

    promo_lookup = (
        promotion_df[
            [
                "ProductUID",
                "VendorUID",
                "MixMatchID"
            ]
        ]
        .drop_duplicates()
    )

    invoice_df = invoice_df.merge(
        promo_lookup,
        on=[
            "ProductUID",
            "VendorUID"
        ],
        how="left"
    )

    cost_df = cost_df.merge(
        promo_lookup,
        on=[
            "ProductUID",
            "VendorUID"
        ],
        how="left"
    )

    # ==========================================
    # Compliance Calculation
    # ==========================================

    results = []

    for _, qd in cost_df.iterrows():

        store = qd["StoreID"]
        mixmatch = qd["MixMatchID"]

        start_date = qd["date"]
        end_date = qd["endDate"]

        req_qty = qd["caseQuantity"]
        req_cost = qd["caseCost"]

        invoices = invoice_df[
            (invoice_df["StoreID"] == store)
            &
            (invoice_df["MixMatchID"] == mixmatch)
            &
            (invoice_df["date"] >= start_date)
            &
            (invoice_df["date"] <= end_date)
        ]

        actual_qty = invoices["quantity"].sum()

        if len(invoices) == 0:

            status = "No Purchases"
            lowest_cost = np.nan

        else:

            lowest_cost = invoices["price"].min()

            qty_pass = actual_qty >= req_qty

            cost_pass = (
                invoices["price"] >= req_cost
            ).all()

            if qty_pass and cost_pass:
                status = "Compliant"

            elif not qty_pass and cost_pass:
                status = "Qty Fail"

            elif qty_pass and not cost_pass:
                status = "Cost Fail"

            else:
                status = "Qty & Cost Fail"

        results.append(
            {
                "StoreID": store,
                "Vendor": qd["vendorName"],
                "ProductUID": qd["ProductUID"],
                "ProductName": qd.get(
                    "retailProductName",
                    ""
                ),
                "MixMatchID": mixmatch,
                "RequiredQty": req_qty,
                "ActualQty": actual_qty,
                "RequiredCost": req_cost,
                "LowestCost": lowest_cost,
                "Status": status,
                "StartDate": start_date,
                "EndDate": end_date
            }
        )

    return pd.DataFrame(results)


# =====================================================
# UI
# =====================================================

st.title("QD Compliance Checker")

st.markdown(
    "Upload all four files to generate the compliance report."
)

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

    with st.spinner("Loading files..."):

        cost_df = load_csv(cost_file)
        invoice_df = load_csv(invoice_file)
        promotion_df = load_csv(promotion_file)
        vendor_df = load_csv(vendor_file)

        cost_df, invoice_df, promotion_df, vendor_df = (
            prepare_data(
                cost_df,
                invoice_df,
                promotion_df,
                vendor_df
            )
        )

        compliance_df = build_compliance_report(
            cost_df,
            invoice_df,
            promotion_df,
            vendor_df
        )

    st.success("Compliance Report Generated")

    # =====================================
    # KPIs
    # =====================================

    total = len(compliance_df)

    compliant = (
        compliance_df["Status"]
        == "Compliant"
    ).sum()

    pct = round(
        (compliant / total) * 100,
        2
    ) if total else 0

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Total QD Rows",
        total
    )

    c2.metric(
        "Compliant",
        compliant
    )

    c3.metric(
        "Compliance %",
        f"{pct}%"
    )

    # =====================================
    # Status Breakdown
    # =====================================

    st.subheader("Status Breakdown")

    st.dataframe(
        compliance_df["Status"]
        .value_counts()
        .reset_index()
    )

    # =====================================
    # Failures
    # =====================================

    st.subheader("Failures")

    failures = compliance_df[
        compliance_df["Status"]
        != "Compliant"
    ]

    st.dataframe(
        failures,
        use_container_width=True
    )

    # =====================================
    # Full Results
    # =====================================

    st.subheader("Full Results")

    st.dataframe(
        compliance_df,
        use_container_width=True
    )

    # =====================================
    # Download
    # =====================================

    csv = compliance_df.to_csv(
        index=False
    )

    st.download_button(
        "Download Results",
        csv,
        "qd_compliance_report.csv",
        "text/csv"
    )
