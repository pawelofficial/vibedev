/**
 * Column Lineage Explorer - Frontend Application
 *
 * Interactive SVG-based graph visualization for SQL column lineage.
 */

(function() {
    'use strict';

    // State
    let graphData = null;
    let selectedModel = null;
    let selectedColumn = null;
    let nodePositions = {};
    let columnYPositions = {};
    let viewTransform = { x: 0, y: 0, scale: 1 };
    let isDragging = false;
    let dragStart = { x: 0, y: 0 };

    // Constants
    const NODE_WIDTH = 250;
    const COLUMN_HEIGHT = 20;
    const HEADER_HEIGHT = 32;
    const NODE_PADDING = 10;
    const LAYER_GAP_X = 350;
    const NODE_GAP_Y = 30;

    // Model layer order (left to right)
    const MODEL_LAYERS = {
        'raw_customers': 0,
        'raw_orders': 0,
        'raw_order_items': 0,
        'raw_products': 0,
        'raw_payments': 0,
        'stg_orders_enriched': 1,
        'stg_line_items_priced': 1,
        'int_customer_order_metrics': 2,
        'fct_customer_revenue_daily': 2,
        'mart_customer_ltv_segments': 3,
    };

    // Init
    document.addEventListener('DOMContentLoaded', init);

    async function init() {
        try {
            const resp = await fetch('/api/graph');
            graphData = await resp.json();
            renderSidebar();
            layoutGraph();
            renderGraph();
            setupSearch();
            setupControls();
            // Default focus on mart
            focusMart();
        } catch (err) {
            console.error('Failed to load graph data:', err);
        }
    }

    function renderSidebar() {
        const list = document.getElementById('model-list');
        list.innerHTML = '';
        graphData.nodes.forEach(node => {
            const div = document.createElement('div');
            div.className = 'model-item';
            div.dataset.model = node.id;
            div.innerHTML = `
                <span class="model-type-icon ${node.type}">${node.type === 'table' ? 'T' : 'V'}</span>
                <span>${node.id}</span>
            `;
            div.addEventListener('click', () => selectModel(node.id));
            list.appendChild(div);
        });
    }

    function layoutGraph() {
        // Group nodes by layer
        const layers = {};
        graphData.nodes.forEach(node => {
            const layer = MODEL_LAYERS[node.id] !== undefined ? MODEL_LAYERS[node.id] : 0;
            if (!layers[layer]) layers[layer] = [];
            layers[layer].push(node);
        });

        // Position nodes
        const startX = 50;
        const startY = 50;

        Object.keys(layers).sort((a, b) => a - b).forEach(layerIdx => {
            const layerNodes = layers[layerIdx];
            let y = startY;
            layerNodes.forEach(node => {
                const nodeHeight = HEADER_HEIGHT + (node.columns.length * COLUMN_HEIGHT) + NODE_PADDING * 2;
                nodePositions[node.id] = {
                    x: startX + layerIdx * LAYER_GAP_X,
                    y: y,
                    width: NODE_WIDTH,
                    height: nodeHeight,
                };
                // Track column Y positions
                columnYPositions[node.id] = {};
                node.columns.forEach((col, i) => {
                    columnYPositions[node.id][col.name] = y + HEADER_HEIGHT + NODE_PADDING + (i * COLUMN_HEIGHT) + COLUMN_HEIGHT / 2;
                });
                y += nodeHeight + NODE_GAP_Y;
            });
        });
    }

    function renderGraph() {
        const svg = document.getElementById('lineage-graph');
        svg.innerHTML = '';

        // Create main group for zoom/pan
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.id = 'graph-root';
        svg.appendChild(g);

        // Render edges first (behind nodes)
        renderEdges(g);
        // Render nodes
        renderNodes(g);
        // Apply transform
        applyTransform();
        // Setup pan/zoom
        setupPanZoom(svg);
    }

    function renderEdges(container) {
        const edgeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        edgeGroup.id = 'edges-group';

        graphData.edges.forEach((edge, i) => {
            const sourcePos = nodePositions[edge.source_model];
            const targetPos = nodePositions[edge.target_model];
            if (!sourcePos || !targetPos) return;

            const sourceColY = columnYPositions[edge.source_model]?.[edge.source_column];
            const targetColY = columnYPositions[edge.target_model]?.[edge.target_column];
            if (sourceColY === undefined || targetColY === undefined) return;

            const x1 = sourcePos.x + sourcePos.width;
            const y1 = sourceColY;
            const x2 = targetPos.x;
            const y2 = targetColY;

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const midX = (x1 + x2) / 2;
            path.setAttribute('d', `M${x1},${y1} C${midX},${y1} ${midX},${y2} ${x2},${y2}`);
            path.setAttribute('class', 'lineage-edge');
            path.dataset.sourceModel = edge.source_model;
            path.dataset.sourceColumn = edge.source_column;
            path.dataset.targetModel = edge.target_model;
            path.dataset.targetColumn = edge.target_column;
            edgeGroup.appendChild(path);
        });

        container.appendChild(edgeGroup);
    }

    function renderNodes(container) {
        graphData.nodes.forEach(node => {
            const pos = nodePositions[node.id];
            if (!pos) return;

            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.setAttribute('class', `model-node ${node.type}`);
            g.setAttribute('transform', `translate(${pos.x}, ${pos.y})`);
            g.dataset.model = node.id;

            // Background rect
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('width', pos.width);
            rect.setAttribute('height', pos.height);
            g.appendChild(rect);

            // Title
            const title = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            title.setAttribute('x', 12);
            title.setAttribute('y', 22);
            title.setAttribute('class', 'model-title');
            title.textContent = node.id;
            title.style.cursor = 'pointer';
            title.addEventListener('click', (e) => {
                e.stopPropagation();
                selectModel(node.id);
            });
            g.appendChild(title);

            // Columns
            node.columns.forEach((col, i) => {
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                const y = HEADER_HEIGHT + NODE_PADDING + (i * COLUMN_HEIGHT) + 14;
                text.setAttribute('x', 16);
                text.setAttribute('y', y);
                let cls = 'column-text';
                if (col.is_derived) cls += ' derived';
                text.setAttribute('class', cls);
                text.dataset.model = node.id;
                text.dataset.column = col.name;
                text.textContent = col.is_derived ? `◆ ${col.name}` : `  ${col.name}`;
                text.addEventListener('click', (e) => {
                    e.stopPropagation();
                    selectColumn(node.id, col.name);
                });
                g.appendChild(text);
            });

            container.appendChild(g);
        });
    }

    function selectModel(modelId) {
        selectedModel = modelId;
        selectedColumn = null;

        // Update sidebar
        document.querySelectorAll('.model-item').forEach(el => {
            el.classList.toggle('selected', el.dataset.model === modelId);
        });

        // Show detail
        const node = graphData.nodes.find(n => n.id === modelId);
        if (!node) return;

        const detail = document.getElementById('detail-content');
        detail.innerHTML = `
            <div class="detail-header">
                <div class="model-name">${node.id}</div>
                <div class="type-info">${node.type} · ${node.columns.length} columns</div>
            </div>
            <div class="lineage-direction">
                <h4>Columns (click to inspect)</h4>
                ${node.columns.map(c => `
                    <div class="lineage-item" onclick="window.__selectColumn('${modelId}', '${c.name}')">
                        <span class="lc">${c.name}</span>
                        ${c.is_derived ? ' <span style="color:#ffab40">◆ derived</span>' : ''}
                    </div>
                `).join('')}
            </div>
        `;

        // Highlight edges connected to this model
        highlightModelEdges(modelId);
        updateSelectionLabel(`Model: ${modelId}`);
    }

    function selectColumn(modelId, columnName) {
        selectedModel = modelId;
        selectedColumn = columnName;

        const node = graphData.nodes.find(n => n.id === modelId);
        const col = node?.columns.find(c => c.name === columnName);

        // Get upstream and downstream
        const upstreamEdges = graphData.edges.filter(e => e.target_model === modelId && e.target_column === columnName);
        const downstreamEdges = graphData.edges.filter(e => e.source_model === modelId && e.source_column === columnName);

        const detail = document.getElementById('detail-content');
        detail.innerHTML = `
            <div class="detail-header">
                <div class="model-name">${modelId}</div>
                <div class="column-name">${columnName}</div>
                <div class="type-info">${col?.is_derived ? 'Derived from multiple sources' : 'Direct or single-source'}</div>
            </div>
            ${col?.expression ? `<div class="expression-display">${escapeHtml(col.expression)}</div>` : ''}
            <div class="lineage-direction">
                <h4>⬆ Upstream (${upstreamEdges.length})</h4>
                ${upstreamEdges.length === 0 ? '<div style="color:#666;font-size:12px;padding:4px 8px">Base column (no upstream)</div>' : ''}
                ${upstreamEdges.map(e => `
                    <div class="lineage-item" onclick="window.__selectColumn('${e.source_model}', '${e.source_column}')">
                        <span class="lm">${e.source_model}</span>.<span class="lc">${e.source_column}</span>
                    </div>
                `).join('')}
            </div>
            <div class="lineage-direction">
                <h4>⬇ Downstream (${downstreamEdges.length})</h4>
                ${downstreamEdges.length === 0 ? '<div style="color:#666;font-size:12px;padding:4px 8px">Terminal column (no downstream)</div>' : ''}
                ${downstreamEdges.map(e => `
                    <div class="lineage-item" onclick="window.__selectColumn('${e.target_model}', '${e.target_column}')">
                        <span class="lm">${e.target_model}</span>.<span class="lc">${e.target_column}</span>
                    </div>
                `).join('')}
            </div>
        `;

        highlightColumnEdges(modelId, columnName);
        updateSelectionLabel(`${modelId}.${columnName}`);
    }

    // Expose to inline onclick handlers
    window.__selectColumn = selectColumn;

    function highlightModelEdges(modelId) {
        document.querySelectorAll('.lineage-edge').forEach(edge => {
            edge.classList.remove('highlighted', 'upstream', 'downstream');
            if (edge.dataset.sourceModel === modelId) {
                edge.classList.add('highlighted', 'downstream');
            } else if (edge.dataset.targetModel === modelId) {
                edge.classList.add('highlighted', 'upstream');
            }
        });

        // Highlight column texts
        document.querySelectorAll('.column-text').forEach(el => {
            el.classList.remove('selected', 'highlighted');
        });
    }

    function highlightColumnEdges(modelId, columnName) {
        // Collect all upstream and downstream via BFS
        const upstreamSet = new Set();
        const downstreamSet = new Set();

        // BFS upstream
        const upQueue = [{model: modelId, column: columnName}];
        const upVisited = new Set([`${modelId}.${columnName}`]);
        while (upQueue.length > 0) {
            const cur = upQueue.shift();
            graphData.edges.forEach(e => {
                if (e.target_model === cur.model && e.target_column === cur.column) {
                    const key = `${e.source_model}.${e.source_column}`;
                    upstreamSet.add(`${e.source_model}|${e.source_column}|${e.target_model}|${e.target_column}`);
                    if (!upVisited.has(key)) {
                        upVisited.add(key);
                        upQueue.push({model: e.source_model, column: e.source_column});
                    }
                }
            });
        }

        // BFS downstream
        const downQueue = [{model: modelId, column: columnName}];
        const downVisited = new Set([`${modelId}.${columnName}`]);
        while (downQueue.length > 0) {
            const cur = downQueue.shift();
            graphData.edges.forEach(e => {
                if (e.source_model === cur.model && e.source_column === cur.column) {
                    const key = `${e.target_model}.${e.target_column}`;
                    downstreamSet.add(`${e.source_model}|${e.source_column}|${e.target_model}|${e.target_column}`);
                    if (!downVisited.has(key)) {
                        downVisited.add(key);
                        downQueue.push({model: e.target_model, column: e.target_column});
                    }
                }
            });
        }

        // Apply styles
        document.querySelectorAll('.lineage-edge').forEach(edge => {
            edge.classList.remove('highlighted', 'upstream', 'downstream');
            const edgeKey = `${edge.dataset.sourceModel}|${edge.dataset.sourceColumn}|${edge.dataset.targetModel}|${edge.dataset.targetColumn}`;
            if (upstreamSet.has(edgeKey)) {
                edge.classList.add('highlighted', 'upstream');
            } else if (downstreamSet.has(edgeKey)) {
                edge.classList.add('highlighted', 'downstream');
            }
        });

        // Highlight column texts
        document.querySelectorAll('.column-text').forEach(el => {
            el.classList.remove('selected', 'highlighted');
            const key = `${el.dataset.model}.${el.dataset.column}`;
            if (el.dataset.model === modelId && el.dataset.column === columnName) {
                el.classList.add('selected');
            } else if (upVisited.has(key)) {
                el.classList.add('highlighted');
            } else if (downVisited.has(key)) {
                el.classList.add('highlighted');
            }
        });
    }

    function setupSearch() {
        const input = document.getElementById('search-input');
        const results = document.getElementById('search-results');

        input.addEventListener('input', () => {
            const query = input.value.toLowerCase().trim();
            if (!query) {
                results.classList.add('hidden');
                return;
            }

            const matches = [];
            graphData.nodes.forEach(node => {
                if (node.id.includes(query)) {
                    matches.push({ type: 'model', model: node.id, modelType: node.type });
                }
                node.columns.forEach(col => {
                    if (col.name.includes(query)) {
                        matches.push({ type: 'column', model: node.id, column: col.name, modelType: node.type });
                    }
                });
            });

            if (matches.length === 0) {
                results.classList.add('hidden');
                return;
            }

            results.innerHTML = matches.slice(0, 20).map(m => {
                if (m.type === 'model') {
                    return `<div class="search-result-item" data-action="model" data-model="${m.model}">
                        <span class="model-name">${m.model}</span>
                        <span class="type-badge">${m.modelType}</span>
                    </div>`;
                } else {
                    return `<div class="search-result-item" data-action="column" data-model="${m.model}" data-column="${m.column}">
                        <span class="model-name">${m.model}</span>.<span class="column-name">${m.column}</span>
                        <span class="type-badge">${m.modelType}</span>
                    </div>`;
                }
            }).join('');

            results.classList.remove('hidden');

            results.querySelectorAll('.search-result-item').forEach(item => {
                item.addEventListener('click', () => {
                    if (item.dataset.action === 'model') {
                        selectModel(item.dataset.model);
                    } else {
                        selectColumn(item.dataset.model, item.dataset.column);
                    }
                    results.classList.add('hidden');
                    input.value = '';
                });
            });
        });

        // Hide results on click outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-container')) {
                results.classList.add('hidden');
            }
        });
    }

    function setupControls() {
        document.getElementById('btn-reset').addEventListener('click', resetView);
        document.getElementById('btn-focus-mart').addEventListener('click', focusMart);
    }

    function resetView() {
        viewTransform = { x: 0, y: 0, scale: 1 };
        applyTransform();
        // Clear selection
        selectedModel = null;
        selectedColumn = null;
        document.querySelectorAll('.lineage-edge').forEach(e => e.classList.remove('highlighted', 'upstream', 'downstream'));
        document.querySelectorAll('.column-text').forEach(e => e.classList.remove('selected', 'highlighted'));
        document.querySelectorAll('.model-item').forEach(e => e.classList.remove('selected'));
        document.getElementById('detail-content').innerHTML = '<p class="hint">Click a model or column to inspect lineage</p>';
        updateSelectionLabel('');
    }

    function focusMart() {
        // Select the mart model and center view on it
        selectModel('mart_customer_ltv_segments');
        const pos = nodePositions['mart_customer_ltv_segments'];
        if (pos) {
            const svg = document.getElementById('lineage-graph');
            const rect = svg.getBoundingClientRect();
            viewTransform.scale = 0.7;
            viewTransform.x = rect.width / 2 - pos.x * viewTransform.scale - (pos.width / 2) * viewTransform.scale;
            viewTransform.y = 50;
            applyTransform();
        }
    }

    function setupPanZoom(svg) {
        svg.addEventListener('mousedown', (e) => {
            if (e.target === svg || e.target.closest('#edges-group')) {
                isDragging = true;
                dragStart = { x: e.clientX - viewTransform.x, y: e.clientY - viewTransform.y };
                svg.style.cursor = 'grabbing';
            }
        });

        document.addEventListener('mousemove', (e) => {
            if (isDragging) {
                viewTransform.x = e.clientX - dragStart.x;
                viewTransform.y = e.clientY - dragStart.y;
                applyTransform();
            }
        });

        document.addEventListener('mouseup', () => {
            isDragging = false;
            svg.style.cursor = 'grab';
        });

        svg.addEventListener('wheel', (e) => {
            e.preventDefault();
            const scaleFactor = e.deltaY > 0 ? 0.9 : 1.1;
            const newScale = Math.max(0.2, Math.min(3, viewTransform.scale * scaleFactor));

            // Zoom toward mouse position
            const rect = svg.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            viewTransform.x = mouseX - (mouseX - viewTransform.x) * (newScale / viewTransform.scale);
            viewTransform.y = mouseY - (mouseY - viewTransform.y) * (newScale / viewTransform.scale);
            viewTransform.scale = newScale;

            applyTransform();
        });

        svg.style.cursor = 'grab';
    }

    function applyTransform() {
        const root = document.getElementById('graph-root');
        if (root) {
            root.setAttribute('transform',
                `translate(${viewTransform.x}, ${viewTransform.y}) scale(${viewTransform.scale})`);
        }
    }

    function updateSelectionLabel(text) {
        document.getElementById('selection-label').textContent = text;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

})();
