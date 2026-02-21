// Toolkit LLM Gateway Dashboard JavaScript

let charts = {};
let currentTimeRange = 30;

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    
    // Auto-refresh every 60 seconds
    setInterval(refreshDashboard, 60000);
});

async function loadDashboard() {
    try {
        await Promise.all([
            loadSummary(),
            loadTimeSeriesChart(),
            loadModelChart(),
            loadUserChart(),
            loadTeamChart(),
            loadWebhooks()
        ]);
        
        updateLastUpdated();
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

async function loadSummary() {
    try {
        const response = await fetch(`/api/summary?days=${currentTimeRange}`);
        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            
            // Update summary cards
            document.getElementById('total-cost').textContent = 
                `$${data.total_cost.toFixed(2)}`;
            
            // Get performance stats
            const perfResponse = await fetch('/api/performance');
            const perfResult = await perfResponse.json();
            
            if (perfResult.success) {
                const perf = perfResult.data;
                document.getElementById('total-requests').textContent = 
                    perf.total_requests.toLocaleString();
                document.getElementById('avg-latency').textContent = 
                    `${Math.round(perf.avg_latency_ms)}ms`;
                document.getElementById('success-rate').textContent = 
                    `${((1 - perf.error_rate) * 100).toFixed(1)}%`;
            }
        }
    } catch (error) {
        console.error('Error loading summary:', error);
    }
}

async function loadTimeSeriesChart() {
    try {
        const response = await fetch(`/api/time-series?granularity=daily&days=${currentTimeRange}`);
        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            
            // Destroy existing chart if it exists
            if (charts.timeSeries) {
                charts.timeSeries.destroy();
            }
            
            const ctx = document.getElementById('timeSeriesChart').getContext('2d');
            charts.timeSeries = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(d => d.period),
                    datasets: [{
                        label: 'Total Cost ($)',
                        data: data.map(d => d.total_cost),
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return '$' + value.toFixed(2);
                                }
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error loading time series chart:', error);
    }
}

async function loadModelChart() {
    try {
        const response = await fetch('/api/cost-by-model?limit=5');
        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            
            if (charts.model) {
                charts.model.destroy();
            }
            
            const ctx = document.getElementById('modelChart').getContext('2d');
            charts.model = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(d => d.model),
                    datasets: [{
                        label: 'Cost ($)',
                        data: data.map(d => d.total_cost),
                        backgroundColor: [
                            '#2563eb',
                            '#3b82f6',
                            '#60a5fa',
                            '#93c5fd',
                            '#dbeafe'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return '$' + value.toFixed(2);
                                }
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error loading model chart:', error);
    }
}

async function loadUserChart() {
    try {
        const response = await fetch('/api/cost-by-user?limit=5');
        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            
            if (charts.user) {
                charts.user.destroy();
            }
            
            const ctx = document.getElementById('userChart').getContext('2d');
            charts.user = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.map(d => d.user_email),
                    datasets: [{
                        data: data.map(d => d.total_cost),
                        backgroundColor: [
                            '#10b981',
                            '#34d399',
                            '#6ee7b7',
                            '#a7f3d0',
                            '#d1fae5'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            position: 'right'
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error loading user chart:', error);
    }
}

async function loadTeamChart() {
    try {
        const response = await fetch('/api/cost-by-team?limit=5');
        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            
            if (charts.team) {
                charts.team.destroy();
            }
            
            const ctx = document.getElementById('teamChart').getContext('2d');
            charts.team = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(d => d.team_name),
                    datasets: [{
                        label: 'Cost ($)',
                        data: data.map(d => d.total_cost),
                        backgroundColor: [
                            '#f59e0b',
                            '#fbbf24',
                            '#fcd34d',
                            '#fde68a',
                            '#fef3c7'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    indexAxis: 'y',
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return '$' + value.toFixed(2);
                                }
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Error loading team chart:', error);
    }
}

async function loadWebhooks() {
    try {
        const response = await fetch('/api/webhooks');
        const result = await response.json();
        
        if (result.success) {
            const webhooks = result.data;
            const container = document.getElementById('webhooks-table');
            
            if (webhooks.length === 0) {
                container.innerHTML = '<p class="loading">No webhooks configured</p>';
                return;
            }
            
            let html = '<table><thead><tr>';
            html += '<th>Name</th>';
            html += '<th>Provider</th>';
            html += '<th>Status</th>';
            html += '<th>Success Rate</th>';
            html += '<th>Total Deliveries</th>';
            html += '</tr></thead><tbody>';
            
            webhooks.forEach(webhook => {
                const stats = webhook.stats || {};
                const successRate = stats.success_rate || 0;
                const statusClass = webhook.enabled ? 'status-enabled' : 'status-disabled';
                const statusText = webhook.enabled ? 'Enabled' : 'Disabled';
                
                html += '<tr>';
                html += `<td><strong>${webhook.name}</strong></td>`;
                html += `<td>${webhook.provider}</td>`;
                html += `<td><span class="status-badge ${statusClass}">${statusText}</span></td>`;
                html += `<td>${successRate.toFixed(1)}%</td>`;
                html += `<td>${stats.total_deliveries || 0}</td>`;
                html += '</tr>';
            });
            
            html += '</tbody></table>';
            container.innerHTML = html;
        }
    } catch (error) {
        console.error('Error loading webhooks:', error);
        document.getElementById('webhooks-table').innerHTML = 
            '<p class="loading">Error loading webhooks</p>';
    }
}

function updateLastUpdated() {
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    document.getElementById('last-updated').textContent = timeString;
}

function refreshDashboard() {
    loadDashboard();
}

function changeTimeRange() {
    const select = document.getElementById('time-range');
    currentTimeRange = parseInt(select.value);
    loadDashboard();
}
