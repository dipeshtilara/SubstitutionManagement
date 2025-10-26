# main1.py
import os
import streamlit as st
import pandas as pd
import warnings
import random

warnings.simplefilter(action="ignore", category=FutureWarning)
st.set_page_config(layout="wide")
st.title("Teacher Substitution Scheduler — Daily / Weekly")

# ---------- CONFIG ----------
LOCAL_FILENAME = "timetableNov25.xlsx"   # your uploaded file name
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
        st.info("Place timetableNov25.xlsx next to this script or upload an Excel file (xlsx).")
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
     - Empty/NaN -> False
     - Off-classes (user selected) -> False
     - If period_name is p0 (zero period): only count if 'skill' appears in cell text
     - If cell explicitly indicates 'zero pd' / '0 pd' / 'zero' -> False unless 'skill' present
     - All other cells (including 'optional') count as class
    """
    if pd.isna(val):
        return False
    s = str(val).strip()
    if s == "":
        return False
    s_lower = s.lower()

    # Off-classes exclusion (substring, case-insensitive)
    if off_classes_list:
        for off in off_classes_list:
            if off and off.lower() in s_lower:
                return False

    # p0 special handling: zero period column ignored unless contains 'skill'
    if period_name and period_name.lower() == "p0":
        return "skill" in s_lower

    # explicit zero pd in cell content: ignore unless also mentions skill
    if (("zero pd" in s_lower) or (s_lower == "0 pd") or (s_lower == "zero")) and ("skill" not in s_lower):
        return False

    # otherwise counted (includes 'optional')
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
                    # free teachers: those not absent and having blank in that period
                    free_teachers = filtered_day_df[
                        ((filtered_day_df[period].isna()) | (filtered_day_df[period].astype(str).str.strip() == "")) &
                        (~filtered_day_df['tname'].isin(absent_teachers))
                    ]['tname'].dropna().unique().tolist()
                    random.shuffle(free_teachers)
                    substitute = None
                    for cand in free_teachers:
                        # fairness heuristic: avoid giving same teacher multiple in same half-day
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

    absent_teachers = st.multiselect("Select absent teachers (Daily):", options=day_df['tname'].dropna().unique().tolist())

    if absent_teachers:
        st.write("### Classes handled by selected absent teachers (Daily)")
        st.dataframe(day_df[day_df['tname'].isin(absent_teachers)])

    if st.checkbox("Compute substitutions for this day"):
        subs = arrange_substitutions(day_df, absent_teachers)
        if not subs.empty:
            st.write("### Substitution Schedule (Daily)")
            st.dataframe(subs)
        else:
            st.info("No substitutions found for the selected inputs (Daily).")

    if st.checkbox("Show period counts for teachers (Daily)"):
        counts = []
        for teacher in day_df['tname'].dropna().unique().tolist():
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
    teachers_all = timetable['tname'].dropna().unique().tolist()
    teacher_choice = st.selectbox("Select teacher (or All):", options=["All"] + teachers_all)

    if teacher_choice == "All":
        totals = []
        for teacher in teachers_all:
            rows = timetable[timetable['tname'] == teacher]
            total = 0
            for _, r in rows.iterrows():
                for period in expected_periods:
                    if cell_has_class(r.get(period, None), period):
                        total += 1
            totals.append({"tname": teacher, "total_periods_week": total, "num_days_present": rows['day'].nunique()})
        totals_df = pd.DataFrame(totals).sort_values(by='total_periods_week', ascending=False).reset_index(drop=True)
        st.write("### Weekly total periods for all teachers")
        st.dataframe(totals_df)
    else:
        trows = timetable[timetable['tname'] == teacher_choice].copy()
        if trows.empty:
            st.warning(f"No entries found for teacher: {teacher_choice}")
        else:
            try:
                trows = trows.sort_values(by='day')
            except Exception:
                pass
            st.write(f"### Timetable for {teacher_choice} (Entire Week)")
            st.dataframe(trows)

            total_periods = 0
            per_day = []
            for day_name, grp in trows.groupby('day'):
                day_count = 0
                for _, row in grp.iterrows():
                    for period in expected_periods:
                        if cell_has_class(row.get(period, None), period):
                            day_count += 1
                per_day.append({"day": day_name, "periods_on_day": day_count})
                total_periods += day_count

            st.write(f"**Total periods for {teacher_choice} in the week:** {total_periods}")
            st.write("### Periods per day for this teacher")
            st.dataframe(pd.DataFrame(per_day).sort_values(by='day').reset_index(drop=True))

    # weekly absent selection option
    absent_week = []
    if st.checkbox("Select absent teachers (apply across the week)?"):
        absent_week = st.multiselect("Select absent teachers (Weekly):", options=teachers_all)
        if absent_week:
            st.write("### Classes handled by selected absent teachers (Weekly)")
            st.dataframe(timetable[timetable['tname'].isin(absent_week)])
        else:
            st.info("No absent teachers selected for weekly view.")

    # weekly substitution (per day)
    if st.checkbox("Compute substitutions for the whole week (day-wise)"):
        subs_all = []
        days = timetable['day'].dropna().unique().tolist()
        for d in days:
            day_df = timetable[timetable['day'] == d]
            subs_for_day = arrange_substitutions(day_df, absent_week)
            if not subs_for_day.empty:
                subs_for_day.insert(0, "day", d)
                subs_all.append(subs_for_day)
        if subs_all:
            sub_df_week = pd.concat(subs_all, ignore_index=True)
            st.write("### Substitution Schedule (Weekly, day-wise)")
            st.dataframe(sub_df_week)
        else:
            st.info("No substitutions found across the week (based on selected inputs).")

st.write("---")
st.caption("Notes: p0 (Zero Period) is counted only when it explicitly contains 'skill'. 'optional' periods are counted normally. 'ct' column is not required.")

