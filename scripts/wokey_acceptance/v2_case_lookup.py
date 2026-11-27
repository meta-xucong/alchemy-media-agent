import datetime,gzip,json,re,sqlite3,subprocess,time
from pathlib import Path

target="E-commerce Main Image - Premium Grain Powder Ad Board"
service="alchemy-v2-api"
pid=int(subprocess.check_output(["systemctl","show",service,"-p","MainPID","--value"],text=True))
proc=Path(f"/proc/{pid}")
cwd=(proc/"cwd").resolve()
prefix=b"V2_DATA_DIR="
configured=next((entry[len(prefix):].decode("utf-8") for entry in (proc/"environ").read_bytes().split(b"\x00") if entry.startswith(prefix)),None)
root=Path(configured) if configured else cwd/".v2_data"
db=(root/"repository.sqlite3").resolve()
assert db.is_file() and db.is_relative_to(root.resolve())
revision=subprocess.check_output(["git","-C",str(cwd.parent),"rev-parse","HEAD"],text=True).strip()
with sqlite3.connect(db.as_uri()+"?mode=ro",uri=True,timeout=5) as conn:
    total=conn.execute("SELECT COUNT(*) FROM v2_records WHERE namespace='prompt_cases' AND active=1").fetchone()[0]
    data=conn.execute("""SELECT record_key, active, index_version, json_extract(payload,'$.title'),
        json_extract(payload,'$.category'), json_extract(payload,'$.provider_id')
        FROM v2_records WHERE namespace='prompt_cases' AND
        (lower(trim(json_extract(payload,'$.title')))=lower(?) OR lower(json_extract(payload,'$.title')) LIKE '%grain%powder%')
        ORDER BY active DESC,quality DESC LIMIT 12""",(target,)).fetchall()
rows=[{"case_id":r[0],"active":bool(r[1]),"index_version":r[2],"title":r[3],"category":r[4],"provider":r[5],
       "exact":str(r[3]).strip().casefold()==target.casefold()} for r in data]
print(json.dumps({"v2_live_case_lookup":{"revision":revision,"active_case_count":total,"results":rows}},sort_keys=True))
