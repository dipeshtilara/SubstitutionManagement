import streamlit as st
import pandas as pd
import warnings
import random

warnings.simplefilter(action='ignore', category=FutureWarning)

# Title of the app
st.title("Teacher Substitution Scheduler")

# Step 1: Upload Excel file
# The code now uses 'df' generically so the filename doesn't matter
uploaded_file = st.file_uploader("Upload Timetable (Excel file)", type=["xlsx"], key="unique_key_1")

if uploaded_file:
    # Load the Excel file into a generic Pandas DataFrame 'df'
    df = pd.read_excel(uploaded_file, header=0)
    df.columns = df.columns.str.strip()  # Remove extra spaces from column names

    # Step 2: Select a day
    if 'day' in df.columns:  # Ensure 'day' column exists
        selected_day = st.selectbox("Select a day:", df['day'].unique())
        filtered_timetable = df[df['day'] == selected_day]

        # Display the timetable for the selected day only
        st.write(f"### Timetable for {selected_day}")
        st.dataframe(filtered_timetable)
    else:
        st.error("The 'day' column is missing from the uploaded file.")
        filtered_timetable = df  # Fallback

    # Step 3: Mark absent teachers
    if 'tname' in filtered_timetable.columns:
        absent_teachers = st.multiselect("Select absent teachers:", filtered_timetable['tname'].dropna().unique())
        absent_classes = filtered_timetable[filtered_timetable['tname'].isin(absent_teachers)]

        # Display classes handled by absent teachers
        if absent_teachers:
            st.write("### Classes Handled by Absent Teachers")
            st.dataframe(absent_classes)
        else:
            st.info("No absent teachers selected.")
    else:
        st.error("'tname' column is missing from the uploaded file.")

    # Step 4: Check for off classes
    off_classes = st.checkbox("Mark specific classes as off?")
    off_classes_list = []
    if off_classes:
        # Checking 'ct' column in the generic 'df'
        if 'ct' in df.columns:
            classes_list = df['ct'].dropna().unique()
            off_classes_list = st.multiselect("Select off classes:", classes_list)
        else:
            st.error("'ct' column is missing from the uploaded file.")

    # Step 5: Finding substitution teachers
    def arrange_substitutions(filtered_timetable, absent_teachers, off_classes_list):
        substitutions = []  # Store substitution entries
        
        # Track assigned substitutions to prevent continuous periods
        teacher_list = filtered_timetable['tname'].dropna().unique()
        assigned_substitutes = {teacher: [] for teacher in teacher_list}
        
        for _, row in filtered_timetable.iterrows():
            if row['tname'] in absent_teachers:  # Process only absent teachers
                substitution_entry = {"tname": row['tname']}
                
                for period in [f'p{i}' for i in range(9)]:  # Process each period (P0 to P8)
                    period_val = str(row[period]) if pd.notna(row[period]) else ""
                    
                    # Logic check: If period is not empty and not an 'off' class
                    if period_val.strip() != "" and not any(off_class in period_val for off_class in off_classes_list):
                    
                        # Find teachers with free periods
                        free_teachers = filtered_timetable[
                            ((filtered_timetable[period].isna()) | 
                            (filtered_timetable[period].astype(str).str.strip() == "")) & 
                            (~filtered_timetable['tname'].isin(absent_teachers))
                        ]['tname'].dropna().unique().tolist()
                        
                        # Shuffle for fair rotation
                        random.shuffle(free_teachers)
                        
                        substitute = None
                        for teacher in free_teachers:
                            # Workload constraints
                            first_half = any(p in assigned_substitutes[teacher] for p in ['p0', 'p1', 'p2', 'p3', 'p4'])
                            second_half = any(p in assigned_substitutes[teacher] for p in ['p5', 'p6', 'p7', 'p8'])
                            
                            if period in ['p0', 'p1', 'p2', 'p3', 'p4'] and first_half:
                                continue
                            if period in ['p5', 'p6', 'p7', 'p8'] and second_half:
                                continue
                                
                            substitute = teacher
                            assigned_substitutes[teacher].append(period)
                            break
                        
                        substitution_entry[period] = f"{row[period]}:{substitute}" if substitute else f"{row[period]}:REQUIRED"
                    else:
                        substitution_entry[period] = None
                
                substitutions.append(substitution_entry)
        
        # Prepare final table
        substitution_table = pd.DataFrame(substitutions, columns=['tname'] + [f'p{i}' for i in range(9)])
        
        # Clean up off-class markers from final view
        substitution_table = substitution_table.map(lambda x: None if pd.isna(x) or any(off_class in str(x) for off_class in off_classes_list) else x)
        return substitution_table

    # Run logic and display results
    if absent_teachers:
        substitutions_res = arrange_substitutions(filtered_timetable, absent_teachers, off_classes_list)
        st.write("### Substitution Schedule")
        if not substitutions_res.empty:
            st.dataframe(substitutions_res)
        else:
            st.info("No substitutions needed for the selected criteria.")
