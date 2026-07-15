import glob
import os

for fpath in glob.glob("*.py"):
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Replace the incorrectly escaped triple quotes
    content = content.replace('\\"\\"\\"', '"""')
    
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
