import os

base = os.path.join(os.path.expandvars(r"%OneDrive%"), "C Language")
print("C Language folder contents:")
for root, dirs, files in os.walk(base):
    level = root.replace(base, "").count(os.sep)
    if level > 4:
        del dirs[:]
        continue
    indent = "  " * level
    print(f"{indent}{os.path.basename(root)}/ ({len(files)} files)")
    for f in files[:10]:
        print(f"  {indent}{f}")
