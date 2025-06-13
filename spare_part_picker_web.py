import streamlit as st
import pandas as pd

# === Load Data ===
@st.cache_data
def load_data():
    df = pd.read_csv("Reparero Spare parts_BOM.csv")
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df["Model number"] = df["Model number"].astype(str)
    compatibility = df.groupby("Part #")["Model Name"].unique().apply(lambda x: sorted(set(x))).to_dict()
    return df, compatibility

df, compatibility_map = load_data()

# === Session state initialization ===
if "last_model_number" not in st.session_state:
    st.session_state.last_model_number = ""
if "last_model_name" not in st.session_state:
    st.session_state.last_model_name = ""
if "previous_selection" not in st.session_state:
    st.session_state.previous_selection = []

# === UI Header ===
st.title("🔧 Spare Part Picker")

# === Search Inputs ===
st.header("Step 1: Search by Model")
col1, col2 = st.columns([1, 2])
with col1:
    model_number = st.text_input("Enter Model Number")
with col2:
    model_name = st.text_input("Or search by Model Name")

# Reset selection only if search is cleared
if (
    model_number != st.session_state.last_model_number
    or model_name != st.session_state.last_model_name
):
    if not model_number and not model_name:
        st.session_state.previous_selection = []

# Update last search terms
st.session_state.last_model_number = model_number
st.session_state.last_model_name = model_name

if st.button("🔄 Reset Selection"):
    for key in list(st.session_state.keys()):
        if key.startswith("qty_"):
            del st.session_state[key]
    st.session_state.previous_selection = []


# === Filter Matching Models ===
filtered = pd.DataFrame()
if model_number:
    filtered = df[df["Model number"].str.contains(model_number, case=False)]
elif model_name:
    filtered = df[df["Model Name"].str.lower().str.contains(model_name.lower())]
    if "ne" not in model_name.lower():
        filtered = filtered[~filtered["Model Name"].str.upper().str.contains(" NE")]

if not filtered.empty:
    st.write("### Matching Spare Parts")
    search_term = st.text_input("🔍 Filter parts by name or part number")

    def filter_rows(row):
        combined = f"{row['Part #']} {row['Part Name']}".lower()
        return all(word in combined for word in search_term.lower().split())

    if search_term:
        filtered = filtered[filtered.apply(filter_rows, axis=1)]

    # Deduplicate and prepare dropdown
    filtered = filtered.drop_duplicates(subset=["Part #"]).sort_values(by="Part Name").head(50)
    show_compat = st.toggle("Show compatible models in dropdown", value=False)

    def make_label(row):
        compat = ", ".join(compatibility_map.get(row["Part #"], []))
        return f"{row['Part #']} | {row['Part Name']}" + (f" | Used in: {compat}" if show_compat else "")

    filtered["Label"] = filtered.apply(make_label, axis=1)

    # Part selector
    part_ids = filtered["Part #"].tolist()
    labels = dict(zip(part_ids, filtered["Label"]))
    valid_previous_selection = [pid for pid in st.session_state.previous_selection if pid in part_ids]

    selection = st.multiselect(
        "Select Parts to Order (live filtered)",
        options=part_ids,
        format_func=lambda pid: labels.get(pid, pid),
        default=valid_previous_selection,
        key="part_selector"
    )

    # Update selection into session state
    st.session_state.previous_selection = list(set(st.session_state.previous_selection + selection))

# === Always use full selection for Step 2 and 3 ===
selection = st.session_state.previous_selection

if selection:
    st.subheader("🔗 Compatibility Overview")
    for part_num in selection:
        match = df[df["Part #"] == part_num]
        if match.empty:
            continue
        part_name = match["Part Name"].values[0]
        models = compatibility_map.get(part_num, [])
        with st.expander(f"{part_num} – {part_name}"):
            st.dataframe(pd.DataFrame(models, columns=["Compatible Model"]), use_container_width=True)

    st.header("Step 2: Review and Quantity")
    order_list = []
    for part_num in selection:
        match = df[df["Part #"] == part_num]
        if match.empty:
            continue
        part_row = match.iloc[0]
        qty_key = f"qty_{part_num}"
        if qty_key not in st.session_state:
            st.session_state[qty_key] = 1
        
        qty = st.number_input(
            f"Qty for {part_num} | {part_row['Part Name']}",
            min_value=1, step=1,
            key=qty_key
        )

        order_list.append({
            "Part #": part_num,
            "Part Name": part_row["Part Name"],
            "Model Name": part_row["Model Name"],  # Only show used model
            "Quantity": qty
        })

    if order_list:
        st.header("Step 3: Export")
        export_df = pd.DataFrame(order_list)
        st.dataframe(export_df, use_container_width=True)
        csv = export_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download as CSV", data=csv, file_name="spare_parts_order.csv", mime="text/csv")

else:
    if model_number or model_name:
        st.warning("No matches found. Please refine your search.")
