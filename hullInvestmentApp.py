import json
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

def price_to_number(price_str):
    if price_str:
        # Remove £ and commas
        clean_str = price_str.replace("£", "").replace(",", "")
        try:
            return int(clean_str)
        except ValueError:
            return None
    return None

# ---------------------------
# Function to extract property details
# ---------------------------

def extract_price_with_regex(text):
    """Extract price using regex pattern"""
    price_pattern = r'£[\d,]+(?:\.\d{2})?'  # Matches £200,000 or £200,000.00
    match = re.search(price_pattern, text)
    return match.group(0) if match else None

def scrape_rightmove(url: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    data = {"price": None, "postcode": None, "street": None, "property_type": None}

    # --- Extract price ---
    price_tag = soup.select_one("._1gfnqJ3Vtd1z40MlC0MzXu")
    if price_tag:
        full_text = price_tag.get_text(strip=True)
        data["price"] = extract_price_with_regex(full_text)

    # --- Extract address / street ---
    address_tag = soup.select_one("._2uQQ3SV0eMHL1P6t5ZDo2q")
    if address_tag:
        full_address = address_tag.get_text(strip=True)
        parts = full_address.split(",")
        if len(parts) >= 2:
            data["street"] = parts[0].strip()
            data["postcode"] = parts[-1].strip()
        else:
            data["street"] = full_address.strip()

    # --- Extract property type from Key Features section ---
    prop_type_tag = soup.select_one("article dl > div:first-of-type dd span p")
    if prop_type_tag:
        raw_type = prop_type_tag.get_text(strip=True).lower()
        type_mapping = {
            "apartment": "Flat",
            "flat": "Flat",
            "detached": "Detached House",
            "semi-detached": "Semi-Detached House",
            "terraced": "Terraced House",
            "end of terrace": "End of Terrace House",
            "bungalow": "Bungalow",
        }
        for key, value in type_mapping.items():
            if key in raw_type:
                data["property_type"] = value
                break
        else:
            data["property_type"] = raw_type.title()  # fallback

    return data

# ---------------------------
# Streamlit App
# ---------------------------

st.set_page_config(
    page_title="Hull Buy-to-Let Analyzer",
    layout="wide"
)
st.title("Berry & Bateman Property Enterprises - Dashboard")

# Path to your existing CSV in the project
csv_path = "hullpropertyanalysis/ppd_data.csv"  # update this to your file path

try:
    df = pd.read_csv(csv_path)
except FileNotFoundError:
    st.error(f"CSV file not found at {csv_path}")
    st.stop()

# Enter Rightmove URL
st.sidebar.header("1. Enter Rightmove URL")
rightmove_url = st.sidebar.text_input("Rightmove property URL")

if rightmove_url:
    property_details = scrape_rightmove(rightmove_url)
    price = property_details["price"]
    street_name = property_details["street"]
    property_type = property_details["property_type"]

    st.subheader("🏠 Property Details Extracted from Rightmove")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("<div style='font-weight:bold'>Street Name</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='margin:10'>{price or 'N/A'}</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div style='font-weight:bold'>Street Name</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='margin:10'>{street_name or 'N/A'}</div>", unsafe_allow_html=True)

    with col3:
        st.markdown("<div style='font-weight:bold'>Property Type</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='margin:10'>{property_type or 'N/A'}</div>", unsafe_allow_html=True)

    st.divider()

    # ---------------------------
    # Filter comparable properties
    # ---------------------------
    type_mapping = {
        "Flat": "F",
        "Detached House": "D",
        "Semi-Detached House": "S",
        "Terraced House": "T",
        "End of Terrace House": "E",
        "Bungalow": "B"
    }

    # Convert to Land Registry letter
    land_registry_type = type_mapping.get(property_type)

    # Filter dataframe by street AND property type
    postcode_df = df[
        (df["street"].str.contains(street_name, case=False, na=False)) &
        (df["property_type"] == land_registry_type)
        ]

    if postcode_df.empty:
        st.warning("No comparable properties found in HM Land Registry data for this postcode/street.")
    else:
        with st.expander("Comparable Sold Properties (Same Street & Type in Last 5 Years"):
            st.dataframe(
                postcode_df[["price_paid", "deed_date", "paon", "street", "town", "postcode", "property_type"]]
                .sort_values("deed_date")
            )
        # ---------------------------
        # Median Price and Visualizations
        # ---------------------------
        median_price = postcode_df["price_paid"].median()
        st.write(f"**Median Sold Price in Area:** £{median_price:,.0f}")

        st.divider()

        # ---------------------------
        # Variable Inputs for Investment
        # ---------------------------
        st.sidebar.header("2. Investment Variables")
        deposit_percent = st.sidebar.slider("Deposit %", 0, 100, 25)
        selected_price = st.sidebar.number_input(
            label="Property Price",
            min_value=0,
            value=price_to_number(price),  # default extracted value
            step=100,
            format="%d"
        )
        mortgage_percent = st.sidebar.number_input("Mortgage Interest (%)", 0.0, 10.0, 5.5)
        stamp_duty_percent = 5
        legal_fees = st.sidebar.number_input("Legal Fees (£)", 0, 5000, 2000)
        refurbishment_cost = st.sidebar.number_input("Refurbishment (£)", 0, 50000, 5000)
        estimated_rent = st.sidebar.number_input("Monthly Rent (£)", 0, 5000, 600)
        maintenance = st.sidebar.number_input("Yearly Maintenance (£)", 0, 5000, 800)
        insurance = st.sidebar.number_input("Insurance (£)", 0, 5000, 170)

        # ---------------------------
        # Calculations
        # ---------------------------
        deposit = selected_price * deposit_percent / 100
        stamp_duty = selected_price * stamp_duty_percent / 100
        total_upfront = deposit + stamp_duty + legal_fees + refurbishment_cost
        total_mortgage = (selected_price - deposit) / 100 * mortgage_percent

        # Gross Yield
        gross_yield = (estimated_rent * 12) / selected_price * 100

        # Net Yield (after operating costs, including mortgage interest if you want)
        annual_operating_costs = total_mortgage + maintenance + insurance
        net_yield = ((estimated_rent * 12) - annual_operating_costs) / selected_price * 100

        # Cash-on-Cash Return
        annual_cash_flow = (estimated_rent * 12) - (
                    total_mortgage + maintenance + insurance)
        cash_invested = deposit + stamp_duty + legal_fees + refurbishment_cost
        cash_on_cash_return = (annual_cash_flow / cash_invested) * 100

        # Thresholds for "good/bad" highlighting
        gross_yield_threshold = 6
        net_yield_threshold = 5
        ctc_yield_threshold = 9
        # ---------------------------
        # Dashboard Layout
        # ---------------------------
        # ---------------------------
        # Buy Decision Indicator
        # ---------------------------
        st.subheader("📊 Quick Buy Decision Indicator")

        if selected_price <= median_price and gross_yield >= gross_yield_threshold and net_yield >= net_yield_threshold:
            decision = "Good Buy ✅"
            color = "#28a745"  # green
        elif selected_price > median_price and gross_yield < gross_yield_threshold and net_yield < net_yield_threshold:
            decision = "Not Recommended ❌"
            color = "#dc3545"  # red
        else:
            decision = "Proceed with Caution ⚠️"
            color = "#fd7e14"  # orange

        # Decision Box (big and styled)
        st.markdown(
            f"""
             <div style='
                 padding:30px;
                 background-color:{color};
                 color:white;
                 text-align:center;
                 border-radius:15px;
                 box-shadow:0 4px 10px rgba(0,0,0,0.2);
                 margin-bottom:20px;
             '>
                 <h2 style='margin:0'>{decision}</h2>
             </div>
             """,
            unsafe_allow_html=True
        )
        st.divider()
        # Investment Summary
        st.subheader("💰 Investment Summary")

        # --- Upfront Costs Section ---
        st.markdown(
            "<h4 style='text-decoration: underline;'>Upfront Costs</h4>",
            unsafe_allow_html=True
        )
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("💷 Deposit", f"£{deposit:,.0f}")

        with col2:
            st.metric("🏛 Stamp Duty", f"£{stamp_duty:,.0f}")

        with col3:
            st.metric("📜 Legal Fees", f"£{legal_fees:,.0f}")

        with col4:
            st.metric("🛠 Refurbishment", f"£{refurbishment_cost:,.0f}")

        # --- Totals Section ---
        st.markdown(
            "<h4 style='text-decoration: underline;'>Total Investment & Returns</h4>",
            unsafe_allow_html=True
        )
        col5, col6, col7, col8, col9 = st.columns(5)

        with col5:
            st.metric("Total Upfront Cost", f"£{total_upfront:,.0f}")

        with col6:
            st.metric("Total Mortgage Cost (Yearly Interest)", f"£{total_mortgage:,.0f}")

        with col7:
            delta_gross = gross_yield - gross_yield_threshold
            st.metric(
                "📈 Gross Yield",
                f"{gross_yield:.2f}%",
                delta=f"{delta_gross:+.2f}%"
            )

        with col8:
            delta_net = net_yield - net_yield_threshold
            st.metric(
                "📈 Net Yield",
                f"{net_yield:.2f}%",
                delta=f"{delta_net:+.2f}%"
            )

        with col9:
            delta_coc = cash_on_cash_return - ctc_yield_threshold
            st.metric(
                "📈 Cash on Cash Return",
                f"{cash_on_cash_return:.2f}%",
                delta=f"{delta_coc:+.2f}%"
            )


