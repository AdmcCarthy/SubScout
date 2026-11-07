"""Network chart: build-time layout is deterministic, continuous across frames, on one scale."""

import json
import math

from subscout.layout import network_layout

FRAMES = ["a", "b"]
NODES = {
    "a": [{"id": k, "size": s} for k, s in zip("PQRSTUVW", (9, 6, 5, 3, 2, 2, 1, 1), strict=True)],
    "b": [{"id": k, "size": s} for k, s in zip("PQRS", (8, 5, 3, 1), strict=True)],
}
EDGES = {
    "a": [{"a": x, "b": y, "w": w} for x, y, w in ("PQ5", "PR3", "QS2", "RT1", "TU1", "UV1", "VW1", "PW1")],
    "b": [{"a": x, "b": y, "w": w} for x, y, w in ("PQ4", "PR2", "QS1")],
}


def test_layout_is_deterministic_and_in_unit_box():
    one = network_layout(FRAMES, NODES, EDGES)
    two = network_layout(FRAMES, NODES, EDGES)
    assert one == two
    for fr in FRAMES:
        assert set(one[fr]) == {d["id"] for d in NODES[fr]}
        assert all(0 <= x <= 1 and 0 <= y <= 1 / 1.5 for x, y in one[fr].values())


def test_shared_scale_makes_smaller_network_smaller():
    pos = network_layout(FRAMES, NODES, EDGES)
    spread = {fr: max(math.dist(p, q) for p in pos[fr].values() for q in pos[fr].values()) for fr in FRAMES}
    assert spread["b"] < spread["a"]


def test_nodes_do_not_overlap_heavily():
    pos = network_layout(FRAMES, NODES, EDGES)["a"]
    pts = list(pos.values())
    assert min(math.dist(p, q) for i, p in enumerate(pts) for q in pts[i + 1 :]) > 0.03


def test_network_chart_builds(tmp_path):
    from subscout.build import build

    d = tmp_path / "s"
    (d / "data").mkdir(parents=True)
    (d / "data" / "nodes.json").write_text(
        json.dumps([{"yr": fr, "id": n["id"], "n": n["size"]} for fr in FRAMES for n in NODES[fr]])
    )
    (d / "data" / "edges.json").write_text(
        json.dumps([{"yr": fr, "a": e["a"], "b": e["b"], "w": e["w"]} for fr in FRAMES for e in EDGES[fr]])
    )
    (d / "story.md").write_text(
        "---\ntitle: T\nsources: { s: { name: S } }\n"
        "data: { nodes: data/nodes.json, edges: data/edges.json }\n---\n"
        "::: step\n### One\n\n```chart\nid: net\ntype: network\ndata: nodes\nedges: edges\n"
        "frame: yr\nsize: n\n"
        "weight: w\ntitle: The network shrinks\nsource: s\nconfidence: observed\n```\n:::\n\n"
        "::: step\n### Two\n\n```chart\nuse: net\nframe: b\n```\n:::\n"
    )
    (d / "story.py").write_text("def metrics(d):\n    return {}\n")
    rep = build(d, tmp_path / "o")
    assert rep.errors == []
    html = (tmp_path / "o" / "index.html").read_text()
    payload = json.loads(html.split('id="ss-payload"')[1].split(">", 1)[1].split("</script>")[0])
    fig = payload["figures"]["net"]["data"]
    assert fig["frames"] == ["a", "b"] and len(fig["nodes"]["b"]) == 4
    assert all("x" in n and "y" in n for n in fig["nodes"]["a"])
