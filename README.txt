# Teacher Substitution Scheduler

This is a Streamlit web application for scheduling teacher substitutions based on an uploaded timetable Excel file. The app allows users to:

- Upload a timetable Excel file.
- Select a specific day to view the timetable.
- Mark absent teachers and see the classes they handle.
- Mark specific classes as "off".
- Automatically arrange substitution teachers, ensuring fair rotation and no continuous periods for substitutes.
- View the generated substitution schedule in a tabular format.

## Features

- **Interactive UI**: Built with Streamlit for easy use.
- **Excel Upload**: Accepts `.xlsx` files for timetable data.
- **Dynamic Filtering**: Filter timetable by day and teacher.
- **Substitution Logic**: Assigns free teachers to cover for absentees, avoiding continuous periods.
- **Customizable Off Classes**: Exclude certain classes from substitution.
- **Tabular Output**: Displays results in a clear, editable table.

## How to Run

1. **Clone or Download the Repository**

2. **Install Requirements**

   Make sure you have Python 3.7+ installed. Install dependencies using:

   ```sh
   pip install -r requirements.txt
   ```

3. **Start the Streamlit App**

   ```sh
   streamlit run main1.py
   ```

4. **Usage**

   - Upload your timetable Excel file when prompted.
   - Select the day, mark absent teachers, and optionally mark off classes.
   - View and download the generated substitution schedule.

## File Structure

- [`main1.py`](c:/Users/Admin/.vscode/project_tt/main1.py): Main Streamlit app for teacher substitution scheduling.
- [`requirements.txt`](requirements.txt): Python dependencies for Streamlit Cloud or local use.

## Requirements

- streamlit >= 1.20.0
- pandas >= 1.3.0
- openpyxl >= 3.0.0

## Example

![Streamlit Screenshot](https://streamlit.io/images/brand/streamlit-logo-secondary-colormark-darktext.png)

## License

This project is for educational and internal use.

---

For any issues or suggestions, please open an issue or contact