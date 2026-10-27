"""Copy real resume PDFs from the reference dataset LithiVR/Resumes into data/resumes/hf_XX.pdf"""
import glob
import os
import shutil

from huggingface_hub import snapshot_download

N = 6
path = snapshot_download("LithiVR/Resumes", repo_type="dataset")    # already in cache, so fast
pdfs = sorted(glob.glob(os.path.join(path, "**", "*.pdf"), recursive=True))
os.makedirs("data/resumes", exist_ok=True)
for i, p in enumerate(pdfs[:N], start=1):
    shutil.copy(p, f"data/resumes/hf_{i:02d}.pdf")
    print(f"hf_{i:02d}.pdf  <-  {os.path.basename(p)}")
print(f"copied {min(N, len(pdfs))} of {len(pdfs)} PDFs")