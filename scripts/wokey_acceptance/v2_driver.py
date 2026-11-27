import os,subprocess,sys
from pathlib import Path
svc="alchemy-v2-worker"
pid=int(subprocess.check_output(["systemctl","show",svc,"-p","MainPID","--value"],text=True).strip())
p=Path(f"/proc/{pid}")
env={}
for item in (p/"environ").read_bytes().split(b"\x00"):
    if b"=" in item:
        k,v=item.split(b"=",1); env[os.fsdecode(k)]=os.fsdecode(v)
env.update(PYTHONDONTWRITEBYTECODE="1",PYTHONUNBUFFERED="1")
stat=p.stat()
cwd=(p/"cwd").resolve(strict=True)
assert str(cwd).startswith("/opt/alchemy-media-agent-releases/") and cwd.name=="custom_media_agent_2_0"
print(subprocess.check_output(["git","-C",str(cwd.parent),"rev-parse","HEAD"],text=True).strip(),flush=True)
r=subprocess.run([str(cwd/".venv/bin/python"),"-"],cwd=cwd,env=env,input=sys.stdin.buffer.read(),user=stat.st_uid,group=stat.st_gid,extra_groups=[])
sys.exit(r.returncode)
