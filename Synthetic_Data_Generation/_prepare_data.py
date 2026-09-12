import os
import shutil

dbms_src = r"C:\Users\nsudi\Washington State University (email.wsu.edu)\Urbano-Rendon, Omar - DBMS"
dst = os.path.join(os.path.dirname(__file__), "data", "cpt_s_course_files")
os.makedirs(dst, exist_ok=True)

count = 0
for f in os.listdir(dbms_src):
    ext = os.path.splitext(f)[1].lower()
    if ext not in {'.pdf', '.docx', '.doc', '.pptx', '.ppt', '.txt', '.md', '.csv', '.xlsx'}:
        continue
    src_path = os.path.join(dbms_src, f)
    dst_path = os.path.join(dst, f)
    if not os.path.exists(dst_path):
        shutil.copy2(src_path, dst_path)
        count += 1
        print(f"Copied: {f}")

print(f"Total files copied: {count}")
print(f"Destination: {dst}")
