import json, pathlib

HOST = "web-production-0263f.up.railway.app"
PLACEHOLDER = "<YOUR-RAILWAY-BACKEND>.railway.app"

# --- web/vercel.json ---
vj = pathlib.Path("web/vercel.json").read_text(encoding="utf-8")
assert vj.count(PLACEHOLDER) == 2, "expected 2 placeholders in vercel.json, got %d" % vj.count(PLACEHOLDER)
vj = vj.replace(PLACEHOLDER, HOST)
cfg = json.loads(vj)  # sanity: still valid JSON
cfg["version"] = 2
pathlib.Path("web/vercel.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
print("web/vercel.json:")
print(json.dumps(cfg, indent=2))

# --- VERCEL.md mirror ---
md = pathlib.Path("VERCEL.md").read_text(encoding="utf-8")
md = md.replace("attendance-api.up.railway.app", HOST)  # both the 'e.g.' line and jsonc block
pathlib.Path("VERCEL.md").write_text(md, encoding="utf-8")
print("\nplaceholder remaining in repo files:", PLACEHOLDER in vj, PLACEHOLDER in md)
