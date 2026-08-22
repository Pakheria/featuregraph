import json
from pathlib import Path
from typing import Dict, Any

class HTMLVisualizer:
    """Generates an interactive, standalone HTML Canvas DAG with node search, dependency highlighting, and line inspection."""

    @staticmethod
    def generate(graph_dict: Dict[str, Any], output_path: Path):
        data_json = json.dumps(graph_dict)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FeatureGraph - Visual Topology</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{ background-color: #0B0F17; color: #F1F5F9; font-family: ui-sans-serif, system-ui, sans-serif; }}
        #network {{ height: calc(100vh - 80px); width: 100%; border-radius: 1rem; }}
    </style>
</head>
<body class="p-4 flex flex-col h-screen overflow-hidden">
    <header class="flex items-center justify-between px-4 py-3 bg-[#131B2A] border border-[#1E293B] rounded-2xl mb-3 shadow-lg">
        <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center font-bold text-white shadow-md">FG</div>
            <div>
                <h1 class="font-bold text-sm tracking-wide">FeatureGraph Visualizer</h1>
                <p class="text-xs text-slate-400">AST Line-Indexed Topology Map</p>
            </div>
        </div>
        <div class="flex items-center gap-3">
            <input id="search-input" type="text" placeholder="Filter features / tags..." class="px-3 py-1.5 text-xs bg-[#0B0F17] border border-[#334155] rounded-xl text-white focus:outline-none focus:border-blue-500">
            <span id="stats-badge" class="text-xs px-2.5 py-1 rounded-lg bg-blue-900/30 text-blue-400 font-mono border border-blue-800/40"></span>
        </div>
    </header>

    <div class="flex-1 flex gap-4 min-h-0">
        <!-- Canvas -->
        <div class="flex-1 bg-[#131B2A] border border-[#1E293B] rounded-2xl relative shadow-xl overflow-hidden">
            <div id="network"></div>
        </div>

        <!-- Sidebar Inspector -->
        <div id="inspector" class="w-96 bg-[#131B2A] border border-[#1E293B] rounded-2xl p-5 shadow-xl overflow-y-auto hidden flex flex-col gap-4">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <span id="feat-badge" class="text-xs px-2 py-0.5 rounded font-mono font-bold bg-blue-600/20 text-blue-400 border border-blue-500/30"></span>
                <span id="feat-type" class="text-xs text-slate-400 capitalize"></span>
            </div>
            <div>
                <h2 id="feat-name" class="font-bold text-base text-white"></h2>
                <p id="feat-desc" class="text-xs text-slate-400 mt-1"></p>
            </div>
            
            <div>
                <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Dependencies</h3>
                <div id="feat-deps" class="flex flex-wrap gap-1.5 text-xs"></div>
            </div>

            <div>
                <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Called By</h3>
                <div id="feat-callers" class="flex flex-wrap gap-1.5 text-xs"></div>
            </div>

            <div>
                <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Source Locations</h3>
                <div id="feat-locs" class="flex flex-col gap-2 text-xs"></div>
            </div>
        </div>
    </div>

    <script>
        const rawData = {data_json};
        const nodesArray = [];
        const edgesArray = [];
        
        Object.keys(rawData).forEach(id => {{
            const f = rawData[id];
            nodesArray.push({{
                id: id,
                label: id + "\\n" + (f.name || id).substring(0, 20),
                shape: 'box',
                margin: 10,
                color: {{
                    background: '#1E293B',
                    border: '#3B82F6',
                    highlight: {{ background: '#2563EB', border: '#60A5FA' }}
                }},
                font: {{ color: '#F8FAFC', size: 12, face: 'monospace' }}
            }});

            (f.depends_on || []).forEach(dep => {{
                edgesArray.push({{
                    from: id,
                    to: dep,
                    arrows: 'to',
                    color: {{ color: '#475569', highlight: '#3B82F6' }},
                    smooth: {{ type: 'cubicBezier' }}
                }});
            }});
        }});

        document.getElementById('stats-badge').innerText = Object.keys(rawData).length + ' Features Mapped';

        const container = document.getElementById('network');
        const data = {{ nodes: new vis.DataSet(nodesArray), edges: new vis.DataSet(edgesArray) }};
        const options = {{
            layout: {{ hierarchical: false }},
            physics: {{
                solver: 'forceAtlas2Based',
                forceAtlas2Based: {{ gravitationalConstant: -50, centralGravity: 0.01, springLength: 100 }}
            }}
        }};
        const network = new vis.Network(container, data, options);

        network.on('click', function(params) {{
            if (params.nodes.length > 0) {{
                const featId = params.nodes[0];
                const feat = rawData[featId];
                if (feat) showInspector(featId, feat);
            }}
        }});

        function showInspector(id, f) {{
            const ins = document.getElementById('inspector');
            ins.classList.remove('hidden');
            document.getElementById('feat-badge').innerText = id;
            document.getElementById('feat-name').innerText = f.name || id;
            document.getElementById('feat-desc').innerText = f.description || 'No description provided.';
            
            const depsDiv = document.getElementById('feat-deps');
            depsDiv.innerHTML = (f.depends_on && f.depends_on.length) 
                ? f.depends_on.map(d => `<span class="px-2 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-300 font-mono">${{d}}</span>`).join('')
                : '<span class="text-slate-500 italic">None</span>';

            const callDiv = document.getElementById('feat-callers');
            callDiv.innerHTML = (f.called_by && f.called_by.length) 
                ? f.called_by.map(c => `<span class="px-2 py-0.5 bg-slate-800 border border-slate-700 rounded text-blue-300 font-mono">${{c}}</span>`).join('')
                : '<span class="text-slate-500 italic">None</span>';

            const locsDiv = document.getElementById('feat-locs');
            locsDiv.innerHTML = (f.locations || []).map(l => `
                <div class="p-2 bg-slate-900/60 border border-slate-800 rounded font-mono text-[11px] text-slate-300 flex justify-between">
                    <span class="truncate">${{l.file}}</span>
                    <span class="text-blue-400 ml-2 font-bold shrink-0">L${{l.start_line}}-L${{l.end_line}}</span>
                </div>
            `).join('');
        }}
    </script>
</body>
</html>"""
        output_path.write_text(html_content, encoding="utf-8")
