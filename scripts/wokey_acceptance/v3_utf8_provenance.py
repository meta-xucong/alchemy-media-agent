import collections,datetime,gzip,json,re,subprocess,time
from pathlib import Path


def _project_text_has_encoding_placeholders(value: str | None) -> bool:
    if not value:
        return False
    runs = list(re.finditer(r"[?\uFFFD]{4,}", value))
    if not runs:
        return False
    # A single run of ordinary question punctuation attached to a word is allowed.
    if len(runs) == 1:
        run = runs[0]
        if (
            run.start() > 0
            and run.end() == len(value)
            and value[run.start() - 1].isalnum()
            and "\uFFFD" not in run.group()
        ):
            return False
    markers = sum(len(run.group()) for run in runs)
    return markers * 100 >= 35 * sum(not char.isspace() for char in value)


wanted="/app/.media_storage"
mounts=json.loads(subprocess.check_output(["docker","inspect","--format","{{json .Mounts}}","alchemy-media-agent"],text=True))
base=next(Path(m["Source"]) for m in mounts if m["Destination"]==wanted)
root=(base/"v3_projects").resolve()
if not root.is_relative_to(base.resolve()): raise RuntimeError("unexpected_media_root")
summary=collections.Counter()
projects=[]
for path in root.glob("project_*/project.json"):
    try:
        raw=json.loads(path.read_text(encoding="utf-8"))
        at=datetime.datetime.fromisoformat(raw["created_at"].replace("Z","+00:00")).timestamp()
    except (OSError,ValueError,KeyError):
        continue
    if at<time.time()-14*86400: continue
    summary["projects_examined"]+=1
    bad={}
    for field in ("title","user_goal","short_summary"):
        val=raw.get(field)
        if not isinstance(val,str): continue
        if field in {"title","user_goal"} and _project_text_has_encoding_placeholders(val.strip()):
            summary[field+"_would_block"]+=1
        compact=re.sub(r"\s+","",val)
        if len(compact)<4 or (compact.count("?")+compact.count("\ufffd"))/len(compact)<.35:
            continue
        summary[field+"_suspect"]+=1
        bad[field]=val
        shape="markers_only" if all(c in "?\ufffd" for c in compact) else "mixed"
        summary[field+"_"+shape]+=1
        if shape=="mixed":
            if re.search(r"[?\ufffd]{4,}.+[^\s?.\ufffd]",val): summary[field+"_mixed_interior"]+=1
            if re.search(r"[?\ufffd]{4,}$",val): summary[field+"_mixed_suffix"]+=1
            if re.search(r"[A-Za-z0-9]",val): summary[field+"_mixed_ascii_alnum"]+=1
    if bad: projects.append(at)

rx=re.compile(r'\[([^\]]+)\]\s+"POST /api/v3/creative-agent/projects(?:\?[^ ]*)? HTTP/[^"]+"\s+20[01]\s+[0-9]+\s+"[^"]*"\s+"([^"]*)"')
def client_group(ua):
    ua=ua.lower()
    if "powershell" in ua: return "powershell"
    if "curl/" in ua: return "curl"
    if "python" in ua or "httpx/" in ua: return "python"
    if "node" in ua or "undici" in ua: return "node"
    if "mozilla" in ua: return "browser"
    return "other"
matches=set()
logs=Path("/var/log/nginx")
for file in sorted(logs.glob("*access*")):
    try:
        if not file.is_file() or file.is_symlink() or file.stat().st_size>24*1024*1024: continue
        opener=gzip.open if file.suffix==".gz" else open
        with opener(file,"rt",encoding="utf-8",errors="replace") as fd:
            for line in fd:
                if "POST /api/v3/creative-agent/projects" not in line: continue
                m=rx.search(line)
                if not m: continue
                try: when=datetime.datetime.strptime(m[1],"%d/%b/%Y:%H:%M:%S %z").timestamp()
                except ValueError: continue
                matches.add((when,client_group(m[2])))
    except OSError:
        continue
summary["recent_http_create_matches"]=len(matches)
for when in projects:
    nearby=[(abs(at-when),group) for at,group in matches if abs(at-when)<=2]
    if not nearby:
        summary["correlation_missing"]+=1
    else:
        best=min(d for d,_ in nearby)
        groups={group for d,group in nearby if d==best}
        if len(groups)==1: summary["matched_"+groups.pop()]+=1
        else: summary["correlation_ambiguous"]+=1
print(json.dumps({"v3_utf8_provenance":dict(summary)},sort_keys=True))
