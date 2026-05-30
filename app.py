import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="QD Cost Compliance Report",
    layout="wide"
)


# ==================================================
# HELPERS
# ==================================================

def clean_id(series):
    return (
        series.astype(str)
        .str.strip()
        .str.replace(".0", "", regex=False)
        .str.lstrip("0")
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

    return cost_df, invoice_df


# ==================================================
# COMPLIANCE ENGINE
# ==================================================

def build_compliance_report(cost_df, invoice_df):

    results = []

    for _, row in cost_df.iterrows():

        store = row["StoreID"]
        product = row["ProductUID"]

        expected_cost = row["caseCost"]

        start_date = row["date"]
        end_date = row["endDate"]

        invoices = invoice_df[
            (invoice_df["StoreID"] == store)
            &
            (invoice_df["ProductUID"] == product)
            &
            (invoice_df["date"] >= start_date)
            &
            (invoice_df["date"] <= end_date)
        ]

        if len(invoices) == 0:

            status = "NO INVOICE"

            lowest_cost = np.nan
            variance = np.nan
            total_qty = 0
            overage = 0

        else:

            lowest_cost = invoices["price"].min()

            variance = (
                lowest_cost
                - expected_cost
            )

            total_qty = invoices["quantity"].sum()

            overage = (
                (
                    invoices["price"]
                    - expected_cost
                )
                * invoices["quantity"]
            ).sum()

            status = (
                "PASS"
                if lowest_cost >= expected_cost
                else "FAIL"
            )

        results.append(
            {
                "StoreID": store,
                "Vendor": row["vendorName"],
                "ProductUID": product,
                "ProductName": row["retailProductName"],
                "ProductType": row["category"],
                "Family": row["family"],
                "PackageGroup": row["group"],
                "ExpectedCost": expected_cost,
                "LowestActualCost": lowest_cost,
                "Variance": variance,
                "TotalCases": total_qty,
                "OverageDollars": round(overage, 2),
                "Status": status,
                "StartDate": start_date,
                "EndDate": end_date
            }
        )

    return pd.DataFrame(results)


# ==================================================
# UI
# ==================================================

st.title("QD Cost Compliance Report")

st.markdown(
    "Upload the QD Cost File and Invoice File."
)

cost_file = st.file_uploader(
    "QD Cost File",
    type=["csv"]
)

invoice_file = st.file_uploader(
    "Invoice File",
    type=["csv"]
)

if cost_file and invoice_file:

    with st.spinner("Processing..."):

        cost_df = load_csv(cost_file)
        invoice_df = load_csv(invoice_file)

        cost_df, invoice_df = prepare_data(
            cost_df,
            invoice_df
        )

        compliance_df = build_compliance_report(
            cost_df,
            invoice_df
        )

    # =====================================
    # KPIs
    # =====================================

    total = len(compliance_df)

    passed = (
        compliance_df["Status"]
        == "PASS"
    ).sum()

    failed = (
        compliance_df["Status"]
        == "FAIL"
    ).sum()

    no_invoice = (
        compliance_df["Status"]
        == "NO INVOICE"
    ).sum()

    compliance_pct = round(
        (
            passed /
            (passed + failed)
        ) * 100,
        2
    ) if (passed + failed) else 0

    total_overage = round(
        compliance_df["OverageDollars"].sum(),
        2
    )

    total_cases = int(
        compliance_df["TotalCases"].sum()
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric(
        "Products",
        total
    )

    c2.metric(
        "Pass",
        passed
    )

    c3.metric(
        "Fail",
        failed
    )

    c4.metric(
        "No Invoice",
        no_invoice
    )

    c5.metric(
        "Compliance %",
        f"{compliance_pct}%"
    )

    c6.metric(
        "Overage $",
        f"${total_overage:,.2f}"
    )

    st.metric(
        "Total Cases",
        f"{total_cases:,}"
    )

    # =====================================
    # TABS
    # =====================================

    tab1, tab2, tab3 = st.tabs(
        [
            "Failures",
            "Pass",
            "All Results"
        ]
    )

    with tab1:

        failures = compliance_df[
            compliance_df["Status"]
            == "FAIL"
        ]

        st.dataframe(
            failures.sort_values(
                "Variance"
            ),
            use_container_width=True
        )

    with tab2:

        passed_df = compliance_df[
            compliance_df["Status"]
            == "PASS"
        ]

        st.dataframe(
            passed_df,
            use_container_width=True
        )

    with tab3:

        st.dataframe(
            compliance_df,
            use_container_width=True
        )

    # =====================================
    # DOWNLOAD
    # =====================================

    csv = compliance_df.to_csv(
        index=False
    )

    st.download_button(
        "Download Results",
        csv,
        "qd_cost_compliance_report.csv",
        "text/csv"
    )
