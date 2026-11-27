import json,tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.project_mode.store import PersistentProjectStore
from app import main as runtime

title="\u6625\u65e5\u6d77\u62a5"
goal="\u4e3a\u6625\u65e5\u6d3b\u52a8\u8bbe\u8ba1\u6d77\u62a5\u3002"
route="/api/v3/creative-agent/projects"
with tempfile.TemporaryDirectory(prefix="v3-utf8-release-probe-") as temp:
    root=Path(temp)
    handlers=V3ProductRouteHandlers(project_store=PersistentProjectStore(root))
    with patch.object(runtime,"v3_route_handlers",handlers), patch.object(runtime,"_require_veyra_user_if_enabled",lambda *args,**kwargs:None):
        client=TestClient(runtime.app)
        damaged=client.post(route,json={"title":"API ????","user_goal":goal})
        assert damaged.status_code==422 and damaged.json()["detail"]["code"]=="v3_project_text_encoding_invalid"
        files_after_rejection=len(list(root.glob("project_*/project.json")))
        assert files_after_rejection==0
        good=client.post(route,content=json.dumps({"title":title,"user_goal":goal},ensure_ascii=False).encode("utf-8"),
                         headers={"Content-Type":"application/json; charset=utf-8"})
        assert good.status_code==200
        project=good.json()["project"]
        saved=json.loads((root/project["project_id"]/"project.json").read_text(encoding="utf-8"))
        assert saved["title"]==title and saved["user_goal"]==goal
        assert not (saved.get("job_ids") or [])
        assert len(list(root.glob("project_*/project.json")))==1
        needle=r'title: "API \\u751f\\u56fe\\u793a\\u4f8b"'
        official=all(needle in (Path(runtime.STATIC_DIR)/name).read_text(encoding="utf-8")
                     for name in ("api-access.js","account-access.js"))
        assert official
        print(json.dumps({"v3_utf8_online_isolated":{"bad_http":damaged.status_code,"files_after_rejection":files_after_rejection,
            "utf8_http":good.status_code,"title_and_goal_preserved":True,"official_examples_ascii_safe":official,"image_jobs":0}}))
