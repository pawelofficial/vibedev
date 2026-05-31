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

    // Node drag state
    let nodeDragState = null; // { nodeId, startX, startY, origNodeX, origNodeY, hasMoved }
    const NODE_DRAG_THRESHOLD = 4; // px in screen-space before a press becomes a drag
    const SESSION_KEY = 'vibedev-lineage-positions';
    const SCHEMA_CONFIG_KEY = 'vibedev-postgres-schema-config';

    // Constants
    const NODE_WIDTH = 250;
    const COLUMN_HEIGHT = 20;
    const HEADER_HEIGHT = 32;
    const NODE_PADDING = 10;
    const LAYER_GAP_X = 350;
    const NODE_GAP_Y = 30;

    // Model layer assignments — computed dynamically from graph edges in init()
    let modelLayers = {};

    /**
     * Compute topological layer assignments from graph edges.
     * Nodes with no incoming edges are layer 0 (source/raw tables).
     * All other nodes get layer = max(layer of upstream nodes) + 1.
     */
    function computeModelLayers(nodes, edges) {
        const layers = {};

        // Build adjacency: for each node, collect its upstream (source) nodes
        const upstreamMap = {}; // targetModel -> Set of sourceModels
        const allNodeIds = new Set();
        nodes.forEach(n => {
            allNodeIds.add(n.id);
            upstreamMap[n.id] = new Set();
        });
        edges.forEach(e => {
            if (allNodeIds.has(e.target_model) && allNodeIds.has(e.source_model)) {
                upstreamMap[e.target_model].add(e.source_model);
            }
        });

        // Iteratively assign layers (BFS / Kahn-style)
        // Layer 0: nodes with no upstream dependencies
        const resolved = new Set();
        const queue = [];
        for (const nodeId of allNodeIds) {
            if (upstreamMap[nodeId].size === 0) {
                layers[nodeId] = 0;
                resolved.add(nodeId);
                queue.push(nodeId);
            }
        }

        // Process until all nodes are assigned
        // For each unresolved node, if all its upstreams are resolved,
        // assign layer = max(upstream layers) + 1
        let safety = 0;
        const maxIterations = allNodeIds.size * allNodeIds.size;
        while (resolved.size < allNodeIds.size && safety < maxIterations) {
            safety++;
            for (const nodeId of allNodeIds) {
                if (resolved.has(nodeId)) continue;
                const ups = upstreamMap[nodeId];
                let allResolved = true;
                let maxLayer = 0;
                for (const up of ups) {
                    if (!resolved.has(up)) {
                        allResolved = false;
                        break;
                    }
                    maxLayer = Math.max(maxLayer, layers[up]);
                }
                if (allResolved) {
                    layers[nodeId] = maxLayer + 1;
                    resolved.add(nodeId);
                }
            }
        }

        // Any remaining nodes (e.g. in cycles) get layer 0 as fallback
        for (const nodeId of allNodeIds) {
            if (layers[nodeId] === undefined) {
                layers[nodeId] = 0;
            }
        }

        return layers;
    }

    // Init
    document.addEventListener('DOMContentLoaded', init);

    async function init() {
        try {
            setupSchemaControls();
            await loadGraphData({ focusDefault: true });
            setupSearch();
            setupControls();
        } catch (err) {
            console.error('Failed to load graph data:', err);
        }
    }

    async function loadGraphData({ focusDefault = false } = {}) {
        const resp = await fetch('/api/graph', { cache: 'no-store' });
        if (!resp.ok) {
            throw new Error(`Failed to load graph data (${resp.status})`);
        }

        graphData = await resp.json();
        modelLayers = computeModelLayers(graphData.nodes, graphData.edges);
        nodePositions = {};
        columnYPositions = {};
        renderSidebar();
        layoutGraph();
        renderGraph();

        if (focusDefault) {
            focusMart();
        }
    }

    function renderSidebar() {
        const list = document.getElementById('model-list');
        list.innerHTML = '';
        graphData.nodes.forEach(node => {
            const div = document.createElement('div');
            div.className = 'model-item';
            div.dataset.model = node.id;
            const typeIcon = node.type === 'table' ? 'T' : node.type === 'missing' ? '?' : 'V';
            div.innerHTML = `
                <span class="model-type-icon ${node.type}">${typeIcon}</span>
                <span>${node.id}</span>
            `;
            div.addEventListener('click', () => selectModel(node.id));
            list.appendChild(div);
        });
    }

    function layoutGraph() {
        // Try to restore saved positions from sessionStorage
        const savedPositions = loadPositionsFromSession();

        // Group nodes by layer
        const layers = {};
        graphData.nodes.forEach(node => {
            const layer = modelLayers[node.id] !== undefined ? modelLayers[node.id] : 0;
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

                // Use saved position if available, otherwise compute default
                const saved = savedPositions?.[node.id];
                const posX = saved ? saved.x : startX + layerIdx * LAYER_GAP_X;
                const posY = saved ? saved.y : y;

                nodePositions[node.id] = {
                    x: posX,
                    y: posY,
                    width: NODE_WIDTH,
                    height: nodeHeight,
                };
                // Track column Y positions
                columnYPositions[node.id] = {};
                node.columns.forEach((col, i) => {
                    columnYPositions[node.id][col.name] = posY + HEADER_HEIGHT + NODE_PADDING + (i * COLUMN_HEIGHT) + COLUMN_HEIGHT / 2;
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
        const nodesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        nodesGroup.id = 'nodes-group';

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
                g.appendChild(text);
            });

            // --- Node-level pointer event handlers for drag + click ---
            setupNodeDrag(g, node);

            nodesGroup.appendChild(g);
        });

        container.appendChild(nodesGroup);
    }

    /**
     * Set up pointer-based drag handling on a node <g> element.
     * Uses a 4px movement threshold to disambiguate click from drag.
     * Clicks on title text fire selectModel; clicks on column text fire selectColumn.
     */
    function setupNodeDrag(groupEl, node) {
        groupEl.addEventListener('pointerdown', (e) => {
            // Only primary button
            if (e.button !== 0) return;
            e.stopPropagation();

            // Capture pointer so we get events even if cursor leaves the SVG
            groupEl.setPointerCapture(e.pointerId);

            nodeDragState = {
                nodeId: node.id,
                pointerId: e.pointerId,
                startX: e.clientX,
                startY: e.clientY,
                origNodeX: nodePositions[node.id].x,
                origNodeY: nodePositions[node.id].y,
                hasMoved: false,
                target: e.target,
            };
        });

        groupEl.addEventListener('pointermove', (e) => {
            if (!nodeDragState || nodeDragState.nodeId !== node.id) return;

            const dx = e.clientX - nodeDragState.startX;
            const dy = e.clientY - nodeDragState.startY;

            // Check threshold before activating drag
            if (!nodeDragState.hasMoved) {
                if (Math.abs(dx) < NODE_DRAG_THRESHOLD && Math.abs(dy) < NODE_DRAG_THRESHOLD) {
                    return; // Still within click deadzone
                }
                nodeDragState.hasMoved = true;
                // Raise node to top z-order
                const parent = groupEl.parentNode;
                parent.appendChild(groupEl);
                // Set grabbing cursor on body during drag
                document.body.classList.add('node-dragging');
            }

            // Convert screen delta to graph-space delta (divide by zoom scale)
            const graphDx = dx / viewTransform.scale;
            const graphDy = dy / viewTransform.scale;
            const newX = nodeDragState.origNodeX + graphDx;
            const newY = nodeDragState.origNodeY + graphDy;

            // Update positions
            updateNodePosition(node.id, newX, newY);

            // Update this node's transform
            groupEl.setAttribute('transform', `translate(${newX}, ${newY})`);

            // Surgically update only connected edges
            updateConnectedEdges(node.id);
        });

        groupEl.addEventListener('pointerup', (e) => {
            if (!nodeDragState || nodeDragState.nodeId !== node.id) return;

            groupEl.releasePointerCapture(e.pointerId);

            if (nodeDragState.hasMoved) {
                // Was a drag — save positions
                document.body.classList.remove('node-dragging');
                savePositionsToSession();
            } else {
                // Was a click — dispatch to appropriate handler
                handleNodeClick(nodeDragState.target, node.id);
            }

            nodeDragState = null;
        });

        groupEl.addEventListener('pointercancel', (e) => {
            if (!nodeDragState || nodeDragState.nodeId !== node.id) return;
            groupEl.releasePointerCapture(e.pointerId);
            document.body.classList.remove('node-dragging');
            nodeDragState = null;
        });
    }

    /**
     * Handle a click (not drag) on a node element.
     * Determines whether it was on a column text or the title/background.
     */
    function handleNodeClick(target, nodeId) {
        // Walk up from the click target to find what was clicked
        const colText = target.closest ? target.closest('.column-text') : null;
        if (colText && colText.dataset.column) {
            selectColumn(colText.dataset.model || nodeId, colText.dataset.column);
            return;
        }
        // Title or background — select the model
        selectModel(nodeId);
    }

    /**
     * Update nodePositions and columnYPositions for a given node.
     */
    function updateNodePosition(nodeId, newX, newY) {
        const pos = nodePositions[nodeId];
        const deltaY = newY - pos.y;
        pos.x = newX;
        pos.y = newY;

        // Shift all column Y positions by the same delta
        const colPositions = columnYPositions[nodeId];
        if (colPositions) {
            for (const colName in colPositions) {
                colPositions[colName] += deltaY;
            }
        }
    }

    /**
     * Surgically update only SVG <path> edges connected to the given node.
     * Much more performant than re-rendering all ~167 edges.
     */
    function updateConnectedEdges(nodeId) {
        const edgesGroup = document.getElementById('edges-group');
        if (!edgesGroup) return;

        const paths = edgesGroup.querySelectorAll(
            `path[data-source-model="${nodeId}"], path[data-target-model="${nodeId}"]`
        );

        paths.forEach(path => {
            const srcModel = path.dataset.sourceModel;
            const srcCol = path.dataset.sourceColumn;
            const tgtModel = path.dataset.targetModel;
            const tgtCol = path.dataset.targetColumn;

            const sourcePos = nodePositions[srcModel];
            const targetPos = nodePositions[tgtModel];
            if (!sourcePos || !targetPos) return;

            const sourceColY = columnYPositions[srcModel]?.[srcCol];
            const targetColY = columnYPositions[tgtModel]?.[tgtCol];
            if (sourceColY === undefined || targetColY === undefined) return;

            const x1 = sourcePos.x + sourcePos.width;
            const y1 = sourceColY;
            const x2 = targetPos.x;
            const y2 = targetColY;
            const midX = (x1 + x2) / 2;

            path.setAttribute('d', `M${x1},${y1} C${midX},${y1} ${midX},${y2} ${x2},${y2}`);
        });
    }

    // --- sessionStorage helpers ---

    function savePositionsToSession() {
        try {
            const data = {};
            for (const nodeId in nodePositions) {
                data[nodeId] = { x: nodePositions[nodeId].x, y: nodePositions[nodeId].y };
            }
            sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
        } catch (e) {
            // sessionStorage may be unavailable in some contexts; silently ignore
        }
    }

    function loadPositionsFromSession() {
        try {
            const raw = sessionStorage.getItem(SESSION_KEY);
            if (!raw) return null;
            return JSON.parse(raw);
        } catch (e) {
            return null;
        }
    }

    function clearPositionsFromSession() {
        try {
            sessionStorage.removeItem(SESSION_KEY);
        } catch (e) {
            // ignore
        }
    }

    /**
     * Highlight a node in the SVG graph by adding the 'selected' class.
     * Removes 'selected' from all other .model-node groups first.
     */
    function highlightNodeInGraph(modelId) {
        document.querySelectorAll('.model-node').forEach(el => {
            el.classList.remove('selected');
        });
        const target = document.querySelector(`.model-node[data-model="${modelId}"]`);
        if (target) {
            target.classList.add('selected');
        }
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
        // Highlight the node in the SVG graph
        highlightNodeInGraph(modelId);
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
        // Highlight the parent node in the SVG graph
        highlightNodeInGraph(modelId);
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

            // Clear all search-match highlights first
            document.querySelectorAll('.model-node').forEach(el => {
                el.classList.remove('search-match');
            });

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

            // Apply search-match highlights to matching nodes in the SVG
            const matchedModels = new Set();
            matches.forEach(m => {
                matchedModels.add(m.model);
            });
            matchedModels.forEach(modelId => {
                const nodeEl = document.querySelector(`.model-node[data-model="${modelId}"]`);
                if (nodeEl) {
                    nodeEl.classList.add('search-match');
                }
            });

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
                    // Clear search-match highlights since selection replaces them
                    document.querySelectorAll('.model-node').forEach(el => {
                        el.classList.remove('search-match');
                    });
                });
            });
        });

        // Hide results on click outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-container')) {
                results.classList.add('hidden');
                // Clear search-match highlights when clicking outside search
                document.querySelectorAll('.model-node').forEach(el => {
                    el.classList.remove('search-match');
                });
            }
        });
    }

    function setupControls() {
        document.getElementById('btn-reset').addEventListener('click', resetView);
        document.getElementById('btn-focus-mart').addEventListener('click', focusMart);
    }

    function setupSchemaControls() {
        const dbInput = document.getElementById('schema-db');
        const schemasInput = document.getElementById('schema-schemas');
        const outputInput = document.getElementById('schema-output');
        const button = document.getElementById('btn-generate-schema');
        const status = document.getElementById('schema-status');

        if (!dbInput || !schemasInput || !outputInput || !button || !status) return;

        const saved = loadSchemaConfig();
        dbInput.value = saved.database === 'lineage_app' ? '' : saved.database || '';
        schemasInput.value = saved.schemas || schemasInput.placeholder || 'public';
        outputInput.value = saved.output || outputInput.value || 'schema.txt';

        button.addEventListener('click', async () => {
            const config = {
                database: dbInput.value.trim(),
                schemas: schemasInput.value.trim(),
                output: outputInput.value.trim() || 'schema.txt',
            };
            saveSchemaConfig(config);

            button.disabled = true;
            setSchemaStatus('Regenerating schema.txt...', 'working');

            try {
                const resp = await fetch('/api/generate-schema', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config),
                });
                const result = await resp.json();
                if (!resp.ok || result.error) {
                    throw new Error(result.error || `Request failed (${resp.status})`);
                }

                clearPositionsFromSession();
                await loadGraphData({ focusDefault: true });
                setSchemaStatus(
                    `Generated ${result.table_count} tables and ${result.view_count} views.`,
                    'success'
                );
            } catch (err) {
                console.error('Schema generation failed:', err);
                setSchemaStatus(err.message || 'Schema generation failed.', 'error');
            } finally {
                button.disabled = false;
            }
        });
    }

    function loadSchemaConfig() {
        try {
            return JSON.parse(localStorage.getItem(SCHEMA_CONFIG_KEY) || '{}');
        } catch (_) {
            return {};
        }
    }

    function saveSchemaConfig(config) {
        localStorage.setItem(SCHEMA_CONFIG_KEY, JSON.stringify(config));
    }

    function setSchemaStatus(message, type) {
        const status = document.getElementById('schema-status');
        if (!status) return;
        status.textContent = message;
        status.className = `schema-status ${type || ''}`.trim();
    }

    function resetView() {
        viewTransform = { x: 0, y: 0, scale: 1 };
        // Clear saved positions and re-layout from defaults
        clearPositionsFromSession();
        layoutGraph();
        renderGraph();
        // Clear selection
        selectedModel = null;
        selectedColumn = null;
        document.querySelectorAll('.lineage-edge').forEach(e => e.classList.remove('highlighted', 'upstream', 'downstream'));
        document.querySelectorAll('.column-text').forEach(e => e.classList.remove('selected', 'highlighted'));
        document.querySelectorAll('.model-item').forEach(e => e.classList.remove('selected'));
        document.querySelectorAll('.model-node').forEach(e => e.classList.remove('selected', 'search-match'));
        document.getElementById('detail-content').innerHTML = '<p class="hint">Click a model or column to inspect lineage</p>';
        updateSelectionLabel('');
    }

    function focusMart() {
        // Select the first node from the highest layer and center view on it
        if (!graphData || graphData.nodes.length === 0) return;
        let maxLayer = -1;
        let focusNodeId = null;
        graphData.nodes.forEach(node => {
            const layer = modelLayers[node.id] !== undefined ? modelLayers[node.id] : 0;
            if (layer > maxLayer) {
                maxLayer = layer;
                focusNodeId = node.id;
            }
        });
        if (!focusNodeId) return;
        selectModel(focusNodeId);
        const pos = nodePositions[focusNodeId];
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
