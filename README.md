# FACE_ID

Face-recognition attendance tool.

Usage

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the steps in order:

```powershell
python preprocess.py          # create student_photos/
python face_register.py      # build student_photos/representations_arcface.pkl
python script.py --photo PATH # mark attendance; default PATH is test/test11.jpg
```

Output: `attendance_record.csv` is updated with Present / Absent / False Positive.
