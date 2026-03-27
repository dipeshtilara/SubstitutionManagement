import os
import streamlit as st
import pandas as pd
import warnings
import random

warnings.simplefilter(action="ignore", category=FutureWarning)
st.set_page_config(layout="wide")
st.title("Teacher Substitution Scheduler — Daily / Weekly")

# ---------- CONFIG ----------
LOCAL_FILENAME = "TT_apr26.xlsx"    # your uploaded file name
# expected fallback period columns (if auto-detect fails)
DEFAULT_PERIOD_COUNT = 9  # p0..p8
# ----------------------------


# ---------- LOAD FILE (auto-load local if present, else uploader) ----------
def load_timetable():
    if os.path.exists(LOCAL_FILENAME):
        try:
            df = pd.read_excel(LOCAL_FILENAME, header=0)
            st.success(f"Loaded local file: {LOCAL_FILENAME}")
            return df
        except Exception as e:
            st.error(f"Could not read local file {LOCAL_FILENAME}: {e}")
            # fall through to uploader
    uploaded = st.file_uploader("Upload timetable Excel (xlsx). Required columns: 'day', 'tname', 'p0'..'p8'.", type=["xlsx"])
    if not uploaded:
        st.info("Place TT_apr26.xlsx next to this script or upload an Excel file (xlsx).")
        st.stop()
    try:
        df = pd.read_excel(uploaded, header=0)
        return df
    except Exception as e:
        st.error(f"Could not read uploaded file: {e}")
        st.stop()

timetable = load_timetable()

# Normalize columns to lowercase and strip spaces
timetable.columns = timetable.columns.str.strip().str.lower()

# --- THE FIX: Clean salutations AND convert to Title Case ---
if 'tname' in timetable.columns:
    timetable['tname'] = timetable['tname'].astype(str).str.replace(r'^(MR|MRS|MS|DR|PROF)\.?\s+', '', case=False, regex=True).str.strip().str.title()

# --- DAY ORDERING LOGIC ---
# Define the sequence. Adjust strings if your Excel uses abbreviations (e.g., 'Mon', 'Tue')
day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Clean and convert to Categorical for proper sorting
timetable['day'] = timetable['day'].str.strip().str.capitalize()
timetable['day'] = pd.Categorical(timetable['day'], categories=day_order, ordered=True)
# --------------------------

# Auto-detect period columns (p0, p1, ...). If not present, fallback to default p0..p8
import re
cols = list(timetable.columns)
period_cols = [c for c in cols if re.fullmatch(r'p\d+', c)]
if not period_cols:
    # attempt looser match
    period_cols = [c for c in cols if re.match(r'p[_\-\s]?\d+', c)]
if not period_cols:
    period_cols = [f"p{i}" for i in range(DEFAULT_PERIOD_COUNT)]
expected_periods = sorted(period_cols, key=lambda x: int(re.findall(r'\d+', x)[0]))

# Required columns (ct is NOT required)
required_columns = ['day', 'tname'] + expected_periods
missing_cols = [c for c in required_columns if c not in timetable.columns]
if missing_cols:
    st.error(f"Uploaded file is missing required columns: {missing_cols}")
    st.stop()

# ---------- UI: view mode & off-classes ----------
view_mode = st.radio("Select view mode:", ["Daily", "Weekly"], horizontal=True)

off_classes = st.checkbox("Mark specific classes as off (these will be excluded from counts and substitutions)?")
off_classes_list = []
if off_classes:
    # use any column named 'ct' for class list if present, else collect unique non-empty tokens from period columns
    if 'ct' in timetable.columns:
        classes_list = timetable['ct'].dropna().unique().tolist()
    else:
        sample_vals = []
        for p in expected_periods:
            sample_vals.extend(timetable[p].dropna().astype(str).tolist())
        # keep unique non-empty short strings as suggestions
        classes_list = sorted({s.strip() for s in sample_vals if s and s.strip()} )
    off_classes_list = st.multiselect("Select off class substrings (case-insensitive):", options=classes_list)

# ---------- Helper: determine whether cell counts as class ----------
def cell_has_class(val, period_name=None):
    """
    Return True if this cell counts as a class period.
    """
    if pd.isna(val):
        return False
    s = str(val).strip()
    if s == "":
        return False
    s_lower = s.lower()

    if off_classes_list:
        for off in off_classes_list:
            if off and off.lower() in s_lower:
                return False

    if period_name and period_name.lower() == "p0":
        return "skill" in s_lower

    if (("zero pd" in s_lower) or (s_lower == "0 pd") or (s_lower == "zero")) and ("skill" not in s_lower):
        return False

    return True

# ---------- Substitution allocator (per-day) ----------
def arrange_substitutions(filtered_day_df, absent_teachers):
    expected = expected_periods
    substitutions = []
    teachers = filtered_day_df['tname'].dropna().unique().tolist()
    assigned = {t: [] for t in teachers}
    for _, row in filtered_day_df.iterrows():
        tname = row['tname']
        if pd.isna(tname):
            continue
        if tname in absent_teachers:
            entry = {"tname": tname}
            for period in expected:
                if cell_has_class(row.get(period, None), period):
                    free_teachers = filtered_day_df[
                        ((filtered_day_df[period].isna()) | (filtered_day_df[period].astype(str).str.strip() == "")) &
                        (~filtered_day_df['tname'].isin(absent_teachers))
                    ]['tname'].dropna().unique().tolist()
                    random.shuffle(free_teachers)
                    substitute = None
                    for cand in free_teachers:
                        first_half = any(p in assigned.get(cand, []) for p in expected[:5])
                        second_half = any(p in assigned.get(cand, []) for p in expected[5:])
                        if period in expected[:5] and first_half: continue
                        if period in expected[5:] and second_half: continue
                        substitute = cand
                        assigned.setdefault(cand, []).append(period)
                        break
                    entry[period] = f"{row.get(period)}:{substitute}" if substitute else None
                else:
                    entry[period] = None
            substitutions.append(entry)
    sub_df = pd.DataFrame(substitutions, columns=['tname'] + expected)
    if not sub_df.empty:
        has_any = sub_df.apply(lambda r: any(pd.notna(c) for c in r[1:]), axis=1)
        sub_df = sub_df[has_any].reset_index(drop=True)
    return sub_df

# ---------- DAILY ----------
if view_mode == "Daily":
    days = timetable['day'].dropna().unique().tolist()
    selected_day = st.selectbox("Select day:", options=days)
    day_df = timetable[timetable['day'] == selected_day].copy()
    st.write(f"### Timetable for {selected_day}")
    st.dataframe(day_df)

    # UPDATED: Use selectbox instead of multiselect for keyboard efficiency
    daily_teachers = sorted(day_df['tname'].dropna().unique().tolist())
    
    if 'absent_daily' not in st.session_state:
        st.session_state.absent_daily = []

    # This handles the keyboard selection perfectly - one name at a time
    selected_name = st.selectbox("Select absent teacher (Daily):", 
                                 options=[""] + daily_teachers, 
                                 index=0)
    
    # Auto-add to state without button click when Enter is pressed (value changes)
    if selected_name and selected_name not in st.session_state.absent_daily:
        st.session_state.absent_daily.append(selected_name)

    # Show the list of absent teachers and allow easy removal if mistake happens
    absent_teachers = st.multiselect("List of absent teachers (Daily):", 
                                     options=st.session_state.absent_daily, 
                                     default=st.session_state.absent_daily)
    st.session_state.absent_daily = absent_teachers

    if absent_teachers:
        st.write("### Classes handled by selected absent teachers (Daily)")
        st.dataframe(day_df[day_df['tname'].isin(absent_teachers)])

    
   # if st.checkbox("Compute substitutions for this day"):
       # subs = arrange_substitutions(day_df, absent_teachers)
       # if not subs.empty:
        #    st.write("### Substitution Schedule (Daily)")
       #     st.dataframe(subs)
      #  else:
      #      st.info("No substitutions found for the selected inputs (Daily).")
    #

    if st.checkbox("Show period counts for teachers (Daily)"):
        counts = []
        for teacher in daily_teachers:
            teacher_rows = day_df[day_df['tname'] == teacher]
            c = 0
            for _, r in teacher_rows.iterrows():
                for period in expected_periods:
                    if cell_has_class(r.get(period, None), period):
                        c += 1
            counts.append({"tname": teacher, "periods_today": c})
        counts_df = pd.DataFrame(counts).sort_values(by='periods_today', ascending=False).reset_index(drop=True)
        st.write("### Period counts (Daily)")
        st.dataframe(counts_df)

# ---------- WEEKLY ----------
else:
    st.write("### Weekly view")
    teachers_all = sorted(timetable['tname'].dropna().unique().tolist())
    teacher_choice = st.selectbox("Select teacher (or All):", options=["All"] + teachers_all)

    if teacher_choice == "All":
        totals = []
        for teacher in teachers_all:
            rows = timetable[timetable['tname'] == teacher]
            total = sum(cell_has_class(row.get(p), p) for _, row in rows.iterrows() for p in expected_periods)
            totals.append({"tname": teacher, "total_periods_week": total, "num_days_present": rows['day'].nunique()})
        totals_df = pd.DataFrame(totals).sort_values(by='total_periods_week', ascending=False).reset_index(drop=True)
        st.write("### Weekly total periods for all teachers")
        st.dataframe(totals_df)
    else:
        trows = timetable[timetable['tname'] == teacher_choice].copy()
        if not trows.empty:
            st.write(f"### Timetable for {teacher_choice} (Entire Week)")
            st.dataframe(trows)
            
            per_day = []
            for day_name, grp in trows.groupby('day'):
                day_count = sum(cell_has_class(row.get(p), p) for _, row in grp.iterrows() for p in expected_periods)
                per_day.append({"day": day_name, "periods_on_day": day_count})
            
            per_day_df = pd.DataFrame(per_day)
            per_day_df['day'] = pd.Categorical(per_day_df['day'], categories=day_order, ordered=True)
            st.dataframe(per_day_df.sort_values(by='day').reset_index(drop=True))

    absent_week = []
    if st.checkbox("Select absent teachers (apply across the week)?"):
        absent_week = st.multiselect("Select absent teachers (Weekly):", options=teachers_all)
        if absent_week:
            st.write("### Classes handled by selected absent teachers (Weekly)")
            st.dataframe(timetable[timetable['tname'].isin(absent_week)])

    if st.checkbox("Compute substitutions for the whole week (day-wise)"):
        subs_all = []
        for d in timetable['day'].dropna().unique().tolist():
            day_df = timetable[timetable['day'] == d]
            subs_for_day = arrange_substitutions(day_df, absent_week)
            if not subs_for_day.empty:
                subs_for_day.insert(0, "day", d)
                subs_all.append(subs_for_day)
        if subs_all:
            st.write("### Substitution Schedule (Weekly, day-wise)")
            st.dataframe(pd.concat(subs_all, ignore_index=True))

st.write("---")
st.caption("Notes: p0 (Zero Period) is counted only when it explicitly contains 'skill'. 'optional' periods are counted normally. 'ct' column is not required.")
