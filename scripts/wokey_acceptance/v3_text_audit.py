import json,os,re,time
from collections import Counter
from pathlib import Path
root=Path(os.getenv("ALCHEMY_V3_PROJECT_DIR") or "/app/.media_storage/v3_projects")
counts=Counter()
def corrupted(value):
    if not isinstance(value,str): return False
    text=re.sub(r"\s+","",value)
    return len(text)>=4 and (text.count("?")+text.count("\ufffd"))/len(text)>=.35
for p in root.rglob("*.json"):
    try:
        if p.stat().st_mtime < time.time()-7*86400: continue
        raw=json.loads(p.read_text(encoding="utf-8"))
    except (OSError,ValueError): continue
    if not isinstance(raw,dict): continue
    doc=raw.get("project") if isinstance(raw.get("project"),dict) else raw
    if not doc.get("project_id") or not any(k in doc for k in ("title","user_goal","short_summary")): continue
    counts["sampled"]+=1
    bad=[k for k in ("title","user_goal","short_summary") if corrupted(doc.get(k))]
    for k in bad: counts[k+"_garbled"]+=1
    if bad:
        counts["any_garbled"]+=1
        if "?" in "".join(str(doc.get(k) or "") for k in bad): counts["literal_ascii_question_marks"]+=1
        if any(doc.get(k) and not corrupted(doc.get(k)) for k in ("title","user_goal","short_summary")):
            counts["has_readable_alternate"]+=1
print(json.dumps({"v3_project_text_audit":{"store_exists":root.is_dir(),**counts}},sort_keys=True))
