import base64
from pathlib import Path
import sys

sets={
    "v2":[
        ("app.services.model_routing","custom_media_agent_2_0/app/services/model_routing.py"),
        ("app.services.claude_orchestrator","custom_media_agent_2_0/app/services/claude_orchestrator.py"),
    ],
    "v3_lab":[
        ("alchemy_creative_agent_3_0.app.model_routing","alchemy_creative_agent_3_0/app/model_routing.py"),
        ("alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider","alchemy_creative_agent_3_0/app/shared_capabilities/visual_cluster/vision_provider.py"),
        ("app.services.alchemy_lab_llm","src_skeleton/app/services/alchemy_lab_llm.py"),
    ],
}
set_name=sys.argv[1]
print("from importlib import import_module as _import_audit_module")
print("from base64 import b64decode as _decode_audit_code")
for name,path in sets[set_name]:
    encoded=base64.b64encode(Path(path).read_bytes()).decode("ascii")
    print(f"_audit_module = _import_audit_module({name!r})")
    print(f"exec(compile(_decode_audit_code({encoded!r}), _audit_module.__file__, 'exec'), vars(_audit_module))")
print(Path(__file__).with_name(set_name+".py").read_text(encoding="utf-8"))
