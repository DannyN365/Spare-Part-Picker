import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# === Load CSV ===
def load_csv():
    df = pd.read_csv("Reparero Spare parts_BOM.csv")
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df["Model number"] = df["Model number"].astype(str)
    return df

df = load_csv()

# === Group parts by compatibility ===
compatibility_map = df.groupby("Part #")["Model Name"].unique().apply(lambda x: ", ".join(sorted(set(x)))).to_dict()

# === App State ===
order_list = []
display_index_map = []

# === Init App ===
root = tk.Tk()
root.title("🙇 Spare Part Picker")

# === Step 1: Search by Model Number or Model Name ===
model_frame = ttk.LabelFrame(root, text="Step 1: Select or Enter Model")
model_frame.pack(fill="x", padx=10, pady=5)

model_entry = ttk.Entry(model_frame)
model_entry.pack(side="left", padx=5, fill="x", expand=True)

model_name_var = tk.StringVar()
model_name_combo = ttk.Combobox(model_frame, textvariable=model_name_var)
model_name_combo.set("-- or search model name --")
model_name_combo.pack(side="left", padx=5, fill="x", expand=True)

# Clear placeholder text on focus
model_name_combo.bind("<FocusIn>", lambda event: model_name_combo.set("") if model_name_combo.get() == "-- or search model name --" else None)

part_listbox = None
current_selection = pd.DataFrame()
selected_part_info = tk.StringVar()


def search_parts():
    global current_selection
    model_number = model_entry.get().strip()
    model_name = model_name_var.get().strip().lower()

    if model_number:
        matches = df[df["Model number"].str.contains(model_number, case=False)]
    elif model_name and model_name != "-- or search model name --":
        matches = df[df["Model Name"].str.lower().str.contains(model_name)]
        if "ne" not in model_name:
            matches = matches[~matches["Model Name"].str.upper().str.contains(" NE")]
    else:
        messagebox.showwarning("Input Error", "Please enter a model number or select a model name.")
        return

    if matches.empty:
        messagebox.showinfo("No Matches", "No parts found for this model.")
        return

    current_selection = matches
    apply_filter()

search_btn = ttk.Button(model_frame, text="🔍 Search", command=search_parts)
search_btn.pack(side="right", padx=5)
model_entry.bind("<Return>", lambda event: search_parts())
model_name_combo.bind("<Return>", lambda event: search_parts())

unique_models = sorted(set(df["Model Name"]))
model_name_combo["values"] = unique_models

# === Step 2: Select Parts ===
part_frame = ttk.LabelFrame(root, text="Step 2: Filter and Select Spare Parts to Order")
part_frame.pack(fill="both", padx=10, pady=5, expand=True)

filter_frame = ttk.Frame(part_frame)
filter_frame.pack(fill="x", padx=5, pady=(5, 0))

filter_label = ttk.Label(filter_frame, text="Filter:")
filter_label.pack(side="left")

filter_entry = ttk.Entry(filter_frame)
filter_entry.pack(side="left", fill="x", expand=True, padx=(5, 2))

info_label = ttk.Label(part_frame, textvariable=selected_part_info, wraplength=600, foreground="gray")
info_label.pack(pady=(0, 5))


def apply_filter(event=None):
    global display_index_map
    keywords = filter_entry.get().strip().lower().split()
    part_listbox.delete(0, tk.END)
    display_index_map = []

    for idx, row in current_selection.iterrows():
        part_id = row["Part #"]
        compat_info = compatibility_map.get(part_id, "")
        combined = f'{part_id} | {row["Part Name"]}'.lower()
        if all(k in combined for k in keywords):
            part_listbox.insert(tk.END, f'{part_id} | {row["Part Name"]}')
            display_index_map.append(idx)

def on_part_select(event):
    try:
        index = part_listbox.curselection()[0]
        row = current_selection.loc[display_index_map[index]]
        compat_models = compatibility_map.get(row["Part #"], "")
        selected_part_info.set(f"Used in: {compat_models}")
    except IndexError:
        selected_part_info.set("")

part_listbox = tk.Listbox(part_frame, selectmode=tk.MULTIPLE, height=10)
part_listbox.pack(fill="both", expand=True, padx=5, pady=5)
part_listbox.bind("<<ListboxSelect>>", on_part_select)


def reset_filter():
    filter_entry.delete(0, tk.END)
    apply_filter()

filter_entry.bind("<Return>", apply_filter)

filter_button = ttk.Button(filter_frame, text="Apply", command=apply_filter)
filter_button.pack(side="left", padx=(2, 2))
clear_button = ttk.Button(filter_frame, text="Clear", command=reset_filter)
clear_button.pack(side="left")


def add_selected_parts():
    selected_indices = part_listbox.curselection()
    if not selected_indices:
        messagebox.showwarning("Selection Error", "Please select at least one part.")
        return

    for i in selected_indices:
        row = current_selection.loc[display_index_map[i]]

        for item in order_list:
            if item["Part #"] == row["Part #"]:
                item["Quantity"] += 1
                update_order_list()
                break
        else:
            order_list.append({
                "Part #": row["Part #"],
                "Part Name": row["Part Name"],
                "Model Name": compatibility_map.get(row["Part #"], row["Model Name"]),
                "Quantity": 1
            })
            update_order_list()

add_btn = ttk.Button(part_frame, text="➕ Add Selected Parts", command=add_selected_parts)
add_btn.pack(pady=5)

# === Step 3: Review & Export ===
review_frame = ttk.LabelFrame(root, text="Step 3: Review Order List and Export")
review_frame.pack(fill="both", padx=10, pady=5, expand=True)

order_tree = ttk.Treeview(review_frame, columns=("Part #", "Part Name", "Model Name", "Quantity"), show="headings")
for col in order_tree["columns"]:
    order_tree.heading(col, text=col)
order_tree.pack(fill="both", expand=True, padx=5, pady=5)


def update_order_list():
    order_tree.delete(*order_tree.get_children())
    for idx, item in enumerate(order_list):
        order_tree.insert("", tk.END, iid=str(idx), values=(
            item["Part #"], item["Part Name"], item["Model Name"], item["Quantity"]
        ))


def edit_quantity_inline(event):
    selected_item = order_tree.identify_row(event.y)
    column = order_tree.identify_column(event.x)
    if not selected_item or column != '#4':
        return

    item_index = int(selected_item)
    x, y, width, height = order_tree.bbox(selected_item, column)

    qty_var = tk.IntVar(value=order_list[item_index]["Quantity"])
    spin = tk.Spinbox(order_tree, from_=1, to=999, textvariable=qty_var, width=5)

    def on_focus_out(_=None):
        try:
            order_list[item_index]["Quantity"] = int(qty_var.get())
            update_order_list()
        except ValueError:
            pass
        spin.destroy()

    spin.place(x=x, y=y, width=width, height=height)
    spin.focus()
    spin.bind("<Return>", on_focus_out)
    spin.bind("<FocusOut>", on_focus_out)

order_tree.bind("<Button-1>", edit_quantity_inline)


def remove_selected_item():
    selected_item = order_tree.focus()
    if not selected_item:
        messagebox.showwarning("No Selection", "Select a row to remove.")
        return
    item_index = int(selected_item)
    del order_list[item_index]
    update_order_list()

remove_btn = ttk.Button(review_frame, text="❌ Remove Selected", command=remove_selected_item)
remove_btn.pack(pady=(0, 5))


# === Export Section ===
def export_to_excel():
    if not order_list:
        messagebox.showwarning("Export Error", "No parts to export.")
        return
    save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
    if save_path:
        export_df = pd.DataFrame(order_list)
        export_df.to_excel(save_path, index=False)
        messagebox.showinfo("Success", f"File saved to:\n{save_path}")

export_btn = ttk.Button(review_frame, text="📄 Export to Excel", command=export_to_excel)
export_btn.pack(pady=5)

root.mainloop()


