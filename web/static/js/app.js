const API_BASE = '/api';
const GRAFANA_URL = '/grafana';
let refreshInterval = null;
let currentPage = 0;
let pageSize = 10;

function init() {
    setupNavigation();
    setupTaskForm();
    setupReportFilters();
    loadInitialData();
    startAutoRefresh();
}

function setupNavigation() {
    const navLinks = document.querySelectorAll('.nav-link[data-section]');
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            if (link.classList.contains('external')) return;
            e.preventDefault();
            const sectionId = link.dataset.section;
            showSection(sectionId);
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
        });
    });
}

function showSection(sectionId) {
    const sections = document.querySelectorAll('.section');
    sections.forEach(s => s.classList.remove('active'));
    const target = document.getElementById(sectionId);
    if (target) target.classList.add('active');
}

function loadInitialData() {
    refreshNodeStatus();
    loadTasks();
    loadReports();
    populateNodeSelect();
}

function startAutoRefresh() {
    refreshInterval = setInterval(() => {
        refreshNodeStatus();
        loadTasks();
    }, 5000);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`API error: ${endpoint}`, error);
        updateConnectionStatus(false);
        throw error;
    }
}

function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('connection-status');
    if (connected) {
        statusEl.textContent = 'Connected';
        statusEl.classList.remove('disconnected');
    } else {
        statusEl.textContent = 'Disconnected';
        statusEl.classList.add('disconnected');
    }
}

function updateLastUpdate() {
    const el = document.getElementById('last-update');
    el.textContent = `Last update: ${new Date().toLocaleTimeString()}`;
}

async function refreshNodeStatus() {
    try {
        const data = await fetchAPI('/nodes');
        renderNodeGrid(data.nodes || []);
        renderMetrics(data.metrics || {});
        updateConnectionStatus(true);
        updateLastUpdate();
    } catch (error) {
        renderNodeGrid([]);
    }
}

function renderNodeGrid(nodes) {
    const grid = document.getElementById('node-grid');
    if (!nodes.length) {
        grid.innerHTML = '<div class="node-card"><p class="status-text">No nodes available</p></div>';
        return;
    }
    grid.innerHTML = nodes.map(node => `
        <div class="node-card">
            <div class="node-card-header">
                <span class="node-id">${node.id}</span>
                <span class="node-role">${node.role}</span>
            </div>
            <div class="node-status">
                <span class="status-indicator ${node.health_status}"></span>
                <span class="status-text">${node.health_status}</span>
            </div>
            <div class="node-url">${node.url}</div>
        </div>
    `).join('');
}

function renderMetrics(metrics) {
    const grid = document.getElementById('metrics-grid');
    const items = [];
    if (metrics.node_up !== undefined) {
        items.push(createMetricItem('node_up', metrics.node_up, metrics.node_up === 1 ? 'active' : 'error'));
    }
    if (metrics.test_running !== undefined) {
        items.push(createMetricItem('test_running', metrics.test_running, metrics.test_running === 1 ? 'active' : ''));
    }
    if (metrics.job_state) {
        items.push(createMetricItem('job_state', metrics.job_state, ''));
    }
    if (metrics.test_verdict) {
        items.push(createMetricItem('test_verdict', metrics.test_verdict, metrics.test_verdict === 'pass' ? 'active' : metrics.test_verdict === 'fail' ? 'error' : 'warning'));
    }
    if (!items.length) {
        grid.innerHTML = '<div class="metric-item"><span class="metric-name">No metrics</span></div>';
        return;
    }
    grid.innerHTML = items.join('');
}

function createMetricItem(name, value, className) {
    return `<div class="metric-item">
        <span class="metric-name">${name}</span>
        <span class="metric-value ${className}">${value}</span>
    </div>`;
}

async function populateNodeSelect() {
    try {
        const data = await fetchAPI('/nodes');
        const select = document.getElementById('task-node');
        const nodes = data.nodes || [];
        select.innerHTML = nodes.map(node => `<option value="${node.id}">${node.id} (${node.role})</option>`).join('');
        if (!nodes.length) {
            select.innerHTML = '<option value="">No nodes available</option>';
        }
    } catch (error) {
        document.getElementById('task-node').innerHTML = '<option value="">Error loading nodes</option>';
    }
}

function setupTaskForm() {
    const form = document.getElementById('task-form');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const taskData = {
            name: formData.get('name'),
            scenario: formData.get('scenario'),
            node_id: formData.get('node_id')
        };
        try {
            await createTask(taskData);
            form.reset();
            loadTasks();
        } catch (error) {
            alert('Failed to create task: ' + error.message);
        }
    });
}

async function createTask(taskData) {
    return await fetchAPI('/tasks', {
        method: 'POST',
        body: JSON.stringify(taskData)
    });
}

async function loadTasks() {
    try {
        const data = await fetchAPI('/tasks');
        renderTaskList(data.tasks || []);
    } catch (error) {
        renderTaskList([]);
    }
}

function renderTaskList(tasks) {
    const list = document.getElementById('task-list');
    if (!tasks.length) {
        list.innerHTML = '<div class="task-item"><p class="status-text">No tasks</p></div>';
        return;
    }
    list.innerHTML = tasks.map(task => `
        <div class="task-item">
            <div class="task-info">
                <span class="task-name">${task.name}</span>
                <span class="task-meta">${task.scenario || 'N/A'} | ${task.created_at || 'N/A'}</span>
            </div>
            <span class="task-status-badge ${task.status}">${task.status}</span>
        </div>
    `).join('');
}

function setupReportFilters() {
    const searchInput = document.getElementById('report-search');
    const verdictFilter = document.getElementById('report-verdict-filter');
    searchInput.addEventListener('input', debounce(() => loadReports(), 300));
    verdictFilter.addEventListener('change', () => loadReports());
}

function debounce(fn, delay) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn(...args), delay);
    };
}

async function loadReports(page = 0) {
    currentPage = page;
    const search = document.getElementById('report-search').value;
    const verdict = document.getElementById('report-verdict-filter').value;
    try {
        const params = new URLSearchParams({
            offset: page * pageSize,
            limit: pageSize
        });
        if (search) params.set('search', search);
        if (verdict) params.set('verdict', verdict);
        const data = await fetchAPI(`/reports?${params}`);
        renderReportTable(data.entries || []);
        renderPagination(data.total || 0, data.offset || 0, data.limit || pageSize);
    } catch (error) {
        renderReportTable([]);
    }
}

function renderReportTable(entries) {
    const tbody = document.getElementById('report-body');
    if (!entries.length) {
        tbody.innerHTML = '<tr><td colspan="4">No reports found</td></tr>';
        return;
    }
    tbody.innerHTML = entries.map(entry => `
        <tr>
            <td>${entry.run_id}</td>
            <td>${formatTimestamp(entry.timestamp)}</td>
            <td><span class="verdict-badge ${entry.verdict}">${entry.verdict}</span></td>
            <td><button class="btn-view" onclick="viewReport('${entry.path}')">View</button></td>
        </tr>
    `).join('');
}

function formatTimestamp(ts) {
    try {
        return new Date(ts).toLocaleString();
    } catch {
        return ts;
    }
}

function renderPagination(total, offset, limit) {
    const pagination = document.getElementById('pagination');
    const totalPages = Math.ceil(total / limit);
    const current = Math.floor(offset / limit);
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }
    const buttons = [];
    buttons.push(`<button class="pagination-btn" onclick="loadReports(${current - 1})" ${current === 0 ? 'disabled' : ''}>Prev</button>`);
    for (let i = 0; i < totalPages; i++) {
        if (i === current) {
            buttons.push(`<button class="pagination-btn active">${i + 1}</button>`);
        } else if (i < 3 || i >= totalPages - 3 || Math.abs(i - current) <= 1) {
            buttons.push(`<button class="pagination-btn" onclick="loadReports(${i})">${i + 1}</button>`);
        } else if (Math.abs(i - current) === 2) {
            buttons.push(`<span style="color: var(--text-muted)">...</span>`);
        }
    }
    buttons.push(`<button class="pagination-btn" onclick="loadReports(${current + 1})" ${current === totalPages - 1 ? 'disabled' : ''}>Next</button>`);
    pagination.innerHTML = buttons.join('');
}

async function viewReport(path) {
    try {
        const data = await fetchAPI(`/reports/detail?path=${encodeURIComponent(path)}`);
        showReportModal(data);
    } catch (error) {
        alert('Failed to load report: ' + error.message);
    }
}

function showReportModal(data) {
    const modal = document.getElementById('report-modal');
    const detail = document.getElementById('report-detail');
    detail.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
    modal.style.display = 'flex';
}

function closeReportModal() {
    document.getElementById('report-modal').style.display = 'none';
}

document.addEventListener('DOMContentLoaded', init);
window.addEventListener('beforeunload', stopAutoRefresh);