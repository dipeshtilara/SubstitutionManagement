import streamlit as st
import pandas as pd
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)


# Title of the app
st.title("Teacher Substitution Scheduler")

# Step 1: Upload Excel file
uploaded_file = st.file_uploader("Upload TimetableOct25 (Excel file)", type=["xlsx"], key="unique_key_1")
if uploaded_file:
    # Load the Excel file into a Pandas DataFrame
    timetableOct25 = pd.read_excel(uploaded_file, header=0)
    timetableOct25.columns = timetableOct25.columns.str.strip()  # Remove extra spaces from column names

    # # Debugging Section (Optional)
    # debug_mode = st.checkbox("Enable debugging?")
    # if debug_mode:
    #     st.write("### Debugging Information")
    #     st.write("Column Names:", list(timetableOct25.columns))
    #     st.write("First Few Rows:")
    #     st.dataframe(timetableOct25.head())

    # Step 2: Select a day
    if 'day' in timetableOct25.columns:  # Ensure 'day' column exists
        selected_day = st.selectbox("Select a day:", timetableOct25['day'].unique())
        filtered_timetable = timetableOct25[timetableOct25['day'] == selected_day]

        # Display the timetable for the selected day only
        st.write(f"### Timetable for {selected_day}")
        st.dataframe(filtered_timetable)
    else:
        st.error("The 'day' column is missing from the uploaded file.")
        filtered_timetable = timetableOct25  # Fallback to unfiltered timetable

    # Step 3: Mark absent teachers
    if 'tname' in filtered_timetable.columns:
        absent_teachers = st.multiselect("Select absent teachers:", filtered_timetable['tname'].dropna().unique())
        absent_classes = filtered_timetable[filtered_timetable['tname'].isin(absent_teachers)]

        # Display classes handled by absent teachers in a tabular structure
        if absent_teachers:
            st.write("### Classes Handled by Absent Teachers")
            st.dataframe(absent_classes)
        else:
            st.info("No absent teachers selected.")
    else:
        st.error("'tname' column is missing from the uploaded file.")

    # Step 4: Check for off classes
    off_classes = st.checkbox("Mark specific classes as off?")
    if off_classes:
        if 'ct' in timetableOct25.columns:
            classes_list = timetableOct25['ct'].dropna().unique()
            off_classes_list = st.multiselect("Select off classes:", classes_list)
        else:
            st.error("'ct' column is missing from the uploaded file.")
            off_classes_list = []
    else:
        off_classes_list = []

    #step 5: finding substitution teachers
    def arrange_substitutions(filtered_timetable, absent_teachers):
        substitutions = []  # Store substitution entries
        # Track assigned substitutions to prevent continuous periods
        assigned_substitutes = {teacher: [] for teacher in filtered_timetable['tname'].dropna().unique()}
        
        for _, row in filtered_timetable.iterrows():
            if row['tname'] in absent_teachers:  # Process only absent teachers
                substitution_entry = {"tname": row['tname']}  # Start substitution entry for absent teacher
                
                for period in [f'p{i}' for i in range(9)]:  # Process each period (P0 to P8)
                    if pd.notna(row[period]) and row[period].strip() != "" and not any(off_class in str(row[period]) for off_class in off_classes_list):
                    
                        # Find teachers with free periods
                        free_teachers = filtered_timetable[
                            ((filtered_timetable[period].isna()) | 
                            (filtered_timetable[period].astype(str).str.strip() == "")) & 
                            (~filtered_timetable['tname'].isin(absent_teachers)) & 
                            (filtered_timetable[period].astype(str).apply(lambda x: not any(off_class in str(x) for off_class in off_classes_list)))
                        ]['tname'].dropna().unique()
                        
                        # Shuffle free teachers for fair rotation
                        #st.write(f"Period {period}: Free Teachers Found →", free_teachers)
                        import random
                        random.shuffle(free_teachers)
                        
                        substitute = None
                        for teacher in free_teachers:
                            first_half = any(p in assigned_substitutes[teacher] for p in ['p0', 'p1', 'p2', 'p3', 'p4'])
                            second_half = any(p in assigned_substitutes[teacher] for p in ['p5', 'p6', 'p7', 'p8'])
                            # Ensure teacher retains at least one free period in the respective half
                            if period in ['p0', 'p1', 'p2', 'p3', 'p4'] and first_half:
                                continue
                            if period in ['p5', 'p6', 'p7', 'p8'] and second_half:
                                continue
                            # Assign substitute and update their assigned periods
                            substitute = teacher
                            assigned_substitutes[teacher].append(period)
                            break
                        #st.write(f"Period {period}: Trying to assign {substitute if substitute else 'REQUIRED'} for class {row[period]}")
                        #st.write(f"Processing {row['tname']} - {period}: {row[period]} (Substituting? {'Yes' if substitute else 'No'})")
                        substitution_entry[period] = (
                            f"{row[period]}:{substitute}" 
                            if substitute and pd.notna(row[period]) and row[period].strip() != "" 
                            else None
                        )


                    else:
                        substitution_entry[period] = None  # No class in this period for absent teacher
                substitutions.append(substitution_entry)
        # Convert substitutions to DataFrame for tabular output
        # Convert substitutions to DataFrame for tabular output
        substitution_table = pd.DataFrame(substitutions, columns=['tname'] + [f'p{i}' for i in range(9)])

        # Strictly enforce removal of off-class periods from the final display
        substitution_table = substitution_table.map(lambda x: None if pd.isna(x) or any(off_class in str(x) for off_class in off_classes_list) else x)

        # Remove rows where all periods are off
        valid_rows = substitution_table.apply(
            lambda row: not all(any(off_class in str(cell) for off_class in off_classes_list) for cell in row[1:]), axis=1
        )
        substitution_table = substitution_table[valid_rows]

        return substitution_table

    # Call the substitution logic
    substitutions_table = arrange_substitutions(filtered_timetable, absent_teachers)
    # Display substitution schedule
    st.write("### Substitution Schedule")
    if not substitutions_table.empty:
        st.write("### Substitution Schedule")
        st.dataframe(substitutions_table)
    else:
        st.info("No substitutions found for the given inputs.")