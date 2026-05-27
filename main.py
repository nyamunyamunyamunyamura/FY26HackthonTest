from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import pandas as pd
import networkx as nx
import json
import os

app = FastAPI(
    title="Corporate Brain - High Reliability Graph Engine",
    description="Render環境用に最適化された、自律型ナレッジネットワーク図配信サービス"
)

# カラーデザインシステム (Modern Dark Theme)
COLORS = {
    "background": "#0F172A",
    "person": "#38BDF8",
    "person_risk": "#FB7185",
    "skill_dept": "#818CF8",
    "project_loc": "#F59E0B",
    "edge": "#334155",
    "text": "#F8FAFC"
}

@app.get("/api/v1/forensics/global-graph", response_class=HTMLResponse)
async def generate_and_serve_graph():
    # 絶対パスを動的に組み立て
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXCEL_PATH = os.path.join(BASE_DIR, "corporate_brain_master_40.xlsx")
    
    if not os.path.exists(EXCEL_PATH):
        raise HTTPException(status_code=404, detail="データソース(Excel)が見つかりません。")

    try:
        # 1. データのロード
        df = pd.read_excel(EXCEL_PATH)

        # 2. NetworkXでグラフ構造を構築
        G = nx.Graph()
        for _, row in df.iterrows():
            person = str(row.get("氏名", "")).strip()
            if not person or person == "nan": continue

            dept = str(row.get("所属部署", "")).strip()
            loc = str(row.get("拠点", "")).strip()
            is_retiring = str(row.get("退職予定フラグ", "")).strip().lower() in ["yes", "true", "y", "1"]
            skills = [s.strip() for s in str(row.get("得意分野", "")).split(",") if s.strip() and s.strip() != "nan"]
            projects = [p.strip() for p in str(row.get("経験領域", "")).split(",") if p.strip() and p.strip() != "nan"]

            G.add_node(person, type="person", is_retiring=is_retiring)

            if dept and dept != "nan":
                G.add_node(dept, type="skill_dept")
                G.add_edge(person, dept)
            if loc and loc != "nan":
                G.add_node(loc, type="project_loc")
                G.add_edge(person, loc)
            for s in skills:
                G.add_node(s, type="skill_dept")
                G.add_edge(person, s)
            for p in projects:
                G.add_node(p, type="project_loc")
                G.add_edge(person, p)

        degree_dict = dict(G.degree)

        # 3. ⭐ Vis.js が直接解読できるJSONデータ構造へ手動マッピング
        vis_nodes = []
        vis_edges = []

        for n in G.nodes():
            attr = G.nodes[n]
            n_type = attr.get("type")

            # 色の決定
            if n_type == "person" and attr.get("is_retiring"):
                color = COLORS["person_risk"]
            elif n_type == "person":
                color = COLORS["person"]
            elif n_type == "skill_dept":
                color = COLORS["skill_dept"]
            else:
                color = COLORS["project_loc"]

            # ノード配列の組み立て
            vis_nodes.append({
                "id": n,
                "label": n,
                "color": color,
                "value": degree_dict[n] * 2, # 繋がりが多いほど大きく
                "title": f"【{str(n_type).upper()}】<br>{n}<br>繋がり数: {degree_dict[n]}", # ホバー
                "font": {"color": COLORS["text"], "size": 14, "face": "sans-serif"}
            })

        for u, v in G.edges():
            # エッジ配列の組み立て
            vis_edges.append({
                "from": u,
                "to": v,
                "color": COLORS["edge"],
                "width": 1.5
            })

        # 4. ⭐ 純粋な HTML / Vis.js テンプレートの動的生成
        # 外部CDN経由で超軽量に読み込ませるため、iPhoneのメモリ負荷も一切ありません
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Corporate Brain Analytics</title>
            <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
            <style type="text/css">
                body, html {{
                    margin: 0; padding: 0; width: 100%; height: 100%;
                    background-color: {COLORS["background"]};
                    overflow: hidden;
                }}
                #network {{
                    width: 100%; height: 100vh;
                }}
            </style>
        </head>
        <body>
            <div id="network"></div>
            <script type="text/javascript">
                var container = document.getElementById('network');
                var data = {{
                    nodes: new vis.DataSet({json.dumps(vis_nodes, ensure_ascii=False)}),
                    edges: new vis.DataSet({json.dumps(vis_edges, ensure_ascii=False)})
                }};
                var options = {{
                    nodes: {{
                        shape: 'dot',
                        borderWidth: 2,
                        borderWidthSelected: 4,
                        scaling: {{ min: 12, max: 35 }}
                    }},
                    edges: {{
                        smooth: {{ type: 'continuous', forceDirection: 'none' }}
                    }},
                    physics: {{
                        forceAtlas2Based: {{
                            gravitationalConstant: -120,
                            centralGravity: 0.01,
                            springLength: 150,
                            springConstant: 0.08
                        }},
                        maxVelocity: 50,
                        solver: 'forceAtlas2Based',
                        timestep: 0.35,
                        stabilization: {{ iterations: 150 }}
                    }},
                    interaction: {{
                        hover: true,
                        hoverConnectedEdges: true,
                        selectConnectedEdges: true,
                        tooltipDelay: 100
                    }}
                }};
                var network = new vis.Network(container, data, options);
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_template, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"内部レンダリングエラー: {str(e)}")
