from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import pandas as pd
import networkx as nx
from pyvis.network import Network
import json
import os

app = FastAPI(
    title="Corporate Brain - Interactive Graph Engine",
    description="HANA/ExcelデータからPyvisのインタラクティブHTMLを動的に生成して配信するサービス"
)

# ==========================================
# カラーデザインシステム (Modern Dark Theme)
# ==========================================
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
    """
    Build AppsのWebビューからアクセスされ、ぐりぐり動くHTMLを画面いっぱいに返すエンドポイント
    """
    # ワークスペース内のエクセルマスタのパスを指定
    EXCEL_PATH = "corporate_brain_master_40.xlsx"
    
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

        # 3. ノード/エッジの装飾スコアリング
        degree_dict = dict(G.degree)
        for n in G.nodes():
            attr = G.nodes[n]
            n_type = attr.get("type")

            if n_type == "person" and attr.get("is_retiring"):
                color = COLORS["person_risk"]
            elif n_type == "person":
                color = COLORS["person"]
            elif n_type == "skill_dept":
                color = COLORS["skill_dept"]
            else:
                color = COLORS["project_loc"]

            G.nodes[n]['label'] = n
            G.nodes[n]['title'] = f"【{n_type.upper()}】\n{n}\n繋がり数: {degree_dict[n]}"
            G.nodes[n]['color'] = color
            G.nodes[n]['value'] = degree_dict[n] * 2
            G.nodes[n]['font'] = {'color': COLORS['text'], 'size': 14, 'face': 'sans-serif'}

        for u, v in G.edges():
            G.edges[u, v]['color'] = COLORS['edge']
            G.edges[u, v]['width'] = 1.5

        # 4. Pyvisの初期化（★本番Web配信サーバー用に調整）
        net = Network(
            height="100vh",      # ⭐Build Appsの画面サイズに追従させるため「100vh」に変更
            width="100%",
            bgcolor=COLORS["background"],
            font_color=COLORS["text"],
            filter_menu=True,
            notebook=False,      # ⭐Colabではないため「False」に修正
            cdn_resources='remote' # ⭐iPhoneのメモリ負荷を下げるため外部CDN読み込みに最適化
        )

        net.from_nx(G)

        # 物理演算オプション設定
        options = {
            "nodes": {"borderWidth": 2, "borderWidthSelected": 4},
            "edges": {"smooth": {"type": "continuous", "forceDirection": "none"}},
            "physics": {
                "forceAtlas2Based": {
                    "gravitationalConstant": -120, "centralGravity": 0.01,
                    "springLength": 150, "springConstant": 0.08
                },
                "maxVelocity": 50, "solver": "forceAtlas2Based", "timestep": 0.35,
                "stabilization": {"iterations": 150}
            },
            "interaction": {
                "hover": True, "hoverConnectedEdges": True, 
                "selectConnectedEdges": True, "tooltipDelay": 100
            }
        }
        net.set_options(json.dumps(options))

        # コンテナ内のローカル一時フォルダにHTMLを一時保存
        temp_html_path = "/tmp/corporate_brain_graph.html"
        net.show(temp_html_path)

        # 保存したHTMLを読み込んでResponseとして返却
        with open(temp_html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        return HTMLResponse(content=html_content, status_code=200)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"内部レンダリングエラー: {str(e)}")

# ローカルデバッグ起動用
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)