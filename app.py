from flask import Flask, request, url_for, redirect, render_template, send_file, send_from_directory
import json
import os
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)
DATA_FILE = 'attendance.json'

# -------- JSON Data Functions --------
def load_attendance():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    return {}

def save_attendance(attendance):
    with open(DATA_FILE, 'w') as file:
        json.dump(attendance, file, indent=4)

def load_students():
    with open('students.json') as f:
        return json.load(f)



# -------- Routes --------

@app.route('/')
def home():
    return render_template('home.html')



@app.route('/dates')
def list_attendance_dates():
    attendance = load_attendance()
    dates = sorted(attendance.keys())
    return render_template('attendance_dates.html', dates=dates)



@app.route('/view/<date>')
def view_attendance_by_date(date):
    attendance = load_attendance()
    students = load_students()
    records = attendance.get(date, [])

    rollno_to_name = {s['rollno']: s['name'] for s in students}
    detailed = [
        {"rollno": r["rollno"], "name": rollno_to_name.get(r["rollno"], "Unknown")}
        for r in records
    ]

    return render_template('attendance_by_date.html', attendance=detailed, selected_date=date)

@app.route('/students')
def students_list():
    with open('students.json') as f:
        students = json.load(f)
    return render_template('students.html', students=students)


@app.route('/add', methods=["GET", "POST"])
def add_attendance():
    attendance = load_attendance()
    students = load_students()
    message = None

    if request.method == 'POST':
        name = request.form['name']
        date = request.form['date']

        # Find student by name to get their rollno
        matched = next((s for s in students if s['name'].strip().lower() == name.strip().lower()), None)
        if not matched:
            message = f"❌ Student '{name}' not found in student list!"
            return render_template("form.html", action="Add", record=None, message=message)

        rollno = matched['rollno']

        if date not in attendance:
            attendance[date] = []

        # Check if already marked present
        if not any(s.get('rollno') == rollno for s in attendance[date]):
            attendance[date].append({ "rollno": rollno })

        save_attendance(attendance)
        return redirect(url_for("view_attendance_by_date", date=date))

    return render_template("form.html", action="Add", record=None, message=message)




@app.route('/update/<date>/<int:id>', methods=["GET", "POST"])
def update_attendance(date, id):
    attendance = load_attendance()
    records = attendance.get(date, [])
    record = next((r for r in records if r['id'] == id), None)

    if not record:
        return "Record not found", 404

    if request.method == 'POST':
        record['name'] = request.form['name']
        save_attendance(attendance)
        return redirect(url_for("view_attendance_by_date", date=date))

    return render_template("form.html", action="Update", record=record, selected_date=date)


@app.route('/delete/<date>/<int:rollno>', methods=["POST"])
def delete_attendance(date, rollno):
    attendance = load_attendance()

    if date in attendance:
        attendance[date] = [r for r in attendance[date] if r.get('rollno') != rollno]

        if not attendance[date]:  # Delete the date if empty
            del attendance[date]

        save_attendance(attendance)

    return redirect(url_for("view_attendance_by_date", date=date))




@app.route('/absent/<date>')
def get_absent_students(date):
    students = load_students()
    attendance = load_attendance()

    records = attendance.get(date, [])
    present_rollnos = {r['rollno'] for r in records}

    absent_students = [
        s for s in students if s['rollno'] not in present_rollnos
    ]

    filepath = f'absentees_{date}.txt'
    with open(filepath, 'w', encoding='utf-8') as f:
        if not absent_students:
            f.write(f"✅ All students were present on {date}.\n")
        else:
            f.write(f"🚫 Absent Students on {date}:\n\n")
            for student in absent_students:
                f.write(f"- {student['name']} (Roll No: {student['rollno']})\n")

    return render_template('absentees_by_date.html', absent_students=absent_students, date=date)

@app.route('/attendance_months')
def attendance_months():
    import calendar

    attendance = load_attendance()

    # Get all months like "2025-06"
    month_keys = sorted({date[:7] for date in attendance})  # YYYY-MM

    # Map to {"2025-06": "June 2025"}
    months = []
    for m in month_keys:
        year, month_num = m.split("-")
        month_name = calendar.month_name[int(month_num)]
        months.append({
            "value": m,  # used in URL
            "label": f"{month_name} {year}"  # shown to user
        })

    return render_template('month_list.html', months=months)

@app.route('/add_student', methods=["GET", "POST"])
def add_student():
    students = load_students()
    message = None

    if request.method == "POST":
        name = request.form["name"].strip()
        rollno = int(request.form["rollno"])

        # Check if roll number already exists
        if any(s["rollno"] == rollno for s in students):
            message = f"❌ Roll No {rollno} already exists."
        else:
            new_id = max([s.get("id", 0) for s in students], default=0) + 1
            students.append({ "id": new_id, "rollno": rollno, "name": name })

            with open('students.json', 'w') as f:
                json.dump(students, f, indent=4)

            return redirect(url_for("students_list"))

    return render_template("add_student.html", message=message)



@app.route('/summary')
def select_month():
    # Extract all months from attendance data
    attendance = load_attendance()
    months = sorted({date[:7] for date in attendance})  # "YYYY-MM"

    return render_template('select_month.html', months=months)

@app.route('/attendance_summary/<month>')
def attendance_summary(month):
    from collections import defaultdict

    students = load_students()
    attendance = load_attendance()

    # Filter only dates that start with the selected month (e.g., '2025-06')
    month_dates = [date for date in attendance if date.startswith(month)]
    total_days = len(month_dates)

    print("📆 Matching Dates for Month:", month_dates)
    print("✅ Total Days:", total_days)

    # Count number of days each rollno was present
    present_counts = defaultdict(int)

    for date in month_dates:
        for entry in attendance[date]:
            rollno = entry.get('rollno')
            if rollno:
                present_counts[rollno] += 1

    # Build final report
    report = []
    for student in students:
        rollno = student['rollno']
        name = student['name']
        present_days = present_counts.get(rollno, 0)
        percentage = (present_days / total_days * 100) if total_days > 0 else 0

        report.append({
            'rollno': rollno,
            'name': name,
            'present_days': present_days,
            'total_days': total_days,
            'percentage': round(percentage, 2)
        })

    # Optional: debug print
    print("🧾 Report:", report)

    return render_template('attendance_summary.html', month=month, students=report)


@app.route('/download_absentees/<date>')
def download_absentees(date):
    filepath = f'absentees_{date}.txt'
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return f"No absentee list found for {date}", 404

# Run app
if __name__ == "__main__":
    app.run(debug=True)
