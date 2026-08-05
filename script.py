from deepface import DeepFace
import pandas as pd
import os
import sys
import argparse
from collections import defaultdict


# List of all enrolled students (ideally, this matches the names of the photo files)
students = ["Ayro", "Noel", "Ojas", "Sanket", "Shreyas", "Udbhav", "Yatharth", "A", "B", "C", "Laksh", "Naman", "Rudra"]

# Paths and defaults
db_path = "student_photos/"
csv_path = "attendance_record.csv"
representations_file = os.path.join(db_path, "representations_arcface.pkl")
default_classroom_photo = "test/test10.jpg"


def ensure_prereqs(photo_path):
    if not os.path.exists(db_path):
        print(f"ERROR: Database folder '{db_path}' not found. Run 'preprocess.py' then 'face_register.py'.")
        sys.exit(1)

    if not os.path.exists(representations_file):
        print(f"ERROR: Embeddings file '{representations_file}' not found. Run 'face_register.py' to build embeddings first.")
        sys.exit(1)

    if not os.path.exists(photo_path):
        print(f"ERROR: Classroom photo '{photo_path}' not found. Provide a valid photo path with --photo.")
        sys.exit(1)


def ensure_csv():
    # Create a dataframe with students marked as 'Absent' by default if CSV missing
    if not os.path.exists(csv_path):
        df = pd.DataFrame({
            "Student_Name": students,
            "Status": ["Absent"] * len(students)
        })
        df.to_csv(csv_path, index=False)
        print("Attendance CSV initialized.")


def crosscheck_students():
    # Compare hardcoded student list to filenames present in student_photos/
    files = [os.path.splitext(f)[0] for f in os.listdir(db_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    set_students = set(students)
    set_files = set(files)

    missing_photos = set_students - set_files
    extra_photos = set_files - set_students

    if missing_photos:
        print("WARNING: These students are in the hardcoded list but have no matching image files:")
        for s in sorted(missing_photos):
            print(" -", s)

    if extra_photos:
        print("NOTICE: These image files exist in 'student_photos/' but are not in the hardcoded student list:")
        for f in sorted(extra_photos):
            print(" -", f)

        # Append extra photos to attendance CSV as 'Absent' so they are tracked
        attendance_df = pd.read_csv(csv_path)
        appended = False
        for f in sorted(extra_photos):
            if f not in attendance_df['Student_Name'].values:
                attendance_df = attendance_df.append({"Student_Name": f, "Status": "Absent"}, ignore_index=True)
                appended = True

        if appended:
            attendance_df.to_csv(csv_path, index=False)
            print("Added extra photo names to attendance CSV as 'Absent'.")


def mark_attendance(photo_path):
    print("Analyzing classroom photo:", photo_path)

    # 1. Crowd Detection & Matching
    results = DeepFace.find(
        img_path=photo_path,
        db_path=db_path,
        model_name="ArcFace",
        detector_backend="retinaface",
        enforce_detection=False
    )

    # Load the master attendance roster
    attendance_df = pd.read_csv(csv_path)

    # Track matched counts to detect duplicates
    match_counts = defaultdict(int)
    matched_details = defaultdict(list)

    # results is a list of Pandas dataframes (one for each face found in the classroom)
    for result_df in results:
        if not result_df.empty:
            matched_path = result_df.iloc[0]['identity']
            filename = os.path.basename(matched_path)
            student_name = os.path.splitext(filename)[0]

            match_counts[student_name] += 1
            matched_details[student_name].append(matched_path)

    # Apply results, marking duplicates as false positives
    for student_name, count in match_counts.items():
        if count > 1:
            attendance_df.loc[attendance_df['Student_Name'] == student_name, 'Status'] = 'False Positive'
            print(f"DUPLICATE MATCH: {student_name} matched {count} times. Marked as False Positive.")
            print("  Matches:")
            for p in matched_details[student_name]:
                print("   -", p)
        else:
            attendance_df.loc[attendance_df['Student_Name'] == student_name, 'Status'] = 'Present'
            print(f"Match found! Marked {student_name} as Present.")

    # Save the updated attendance
    attendance_df.to_csv(csv_path, index=False)
    print("\nAttendance marking complete. CSV updated.")
    print(attendance_df)


def parse_args():
    p = argparse.ArgumentParser(description="Mark attendance from a classroom photo using DeepFace database")
    p.add_argument('--photo', '-p', default=default_classroom_photo, help='Path to classroom photo')
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    photo = args.photo

    ensure_prereqs(photo)
    ensure_csv()
    crosscheck_students()
    mark_attendance(photo)