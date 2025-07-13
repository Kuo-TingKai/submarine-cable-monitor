#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络监控Web仪表板
提供实时网络状态监控界面
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
import sqlite3
from network_monitor import NetworkMonitor

app = FastAPI(title="网络监控仪表板", version="1.0.0")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
        
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # 移除断开的连接
                self.active_connections.remove(connection)

manager = ConnectionManager()
monitor = NetworkMonitor()

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """主仪表板页面"""
    return """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>网络监控仪表板</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            .status-card {
                transition: all 0.3s ease;
            }
            .status-operational { border-left: 4px solid #28a745; }
            .status-degraded { border-left: 4px solid #ffc107; }
            .status-down { border-left: 4px solid #dc3545; }
            .metric-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .alert-card {
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                color: white;
            }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark bg-dark">
            <div class="container-fluid">
                <span class="navbar-brand mb-0 h1">
                    <i class="fas fa-network-wired"></i> 网络监控仪表板
                </span>
                <span class="navbar-text" id="lastUpdate"></span>
            </div>
        </nav>
        
        <div class="container-fluid mt-3">
            <!-- 状态概览 -->
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="card metric-card">
                        <div class="card-body text-center">
                            <h3 id="totalEndpoints">0</h3>
                            <p class="mb-0">总端点</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card metric-card">
                        <div class="card-body text-center">
                            <h3 id="operationalCount">0</h3>
                            <p class="mb-0">正常运行</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card metric-card">
                        <div class="card-body text-center">
                            <h3 id="degradedCount">0</h3>
                            <p class="mb-0">性能下降</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card metric-card">
                        <div class="card-body text-center">
                            <h3 id="downCount">0</h3>
                            <p class="mb-0">完全中断</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 详细状态 -->
            <div class="row">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-header">
                            <h5><i class="fas fa-list"></i> 网络状态详情</h5>
                        </div>
                        <div class="card-body">
                            <div id="statusList"></div>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card alert-card">
                        <div class="card-header">
                            <h5><i class="fas fa-exclamation-triangle"></i> 最近告警</h5>
                        </div>
                        <div class="card-body">
                            <div id="alertList"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            let ws = new WebSocket(`ws://${window.location.host}/ws`);
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            };
            
            ws.onclose = function() {
                console.log('WebSocket连接已关闭');
                setTimeout(() => {
                    location.reload();
                }, 5000);
            };
            
            function updateDashboard(data) {
                // 更新状态概览
                document.getElementById('totalEndpoints').textContent = data.summary.total;
                document.getElementById('operationalCount').textContent = data.summary.operational;
                document.getElementById('degradedCount').textContent = data.summary.degraded;
                document.getElementById('downCount').textContent = data.summary.down;
                
                // 更新最后更新时间
                document.getElementById('lastUpdate').textContent = 
                    `最后更新: ${new Date().toLocaleString('zh-CN')}`;
                
                // 更新状态列表
                updateStatusList(data.status);
                
                // 更新告警列表
                updateAlertList(data.alerts);
            }
            
            function updateStatusList(statusData) {
                const statusList = document.getElementById('statusList');
                statusList.innerHTML = '';
                
                statusData.forEach(item => {
                    const statusClass = `status-${item.status}`;
                    const statusIcon = getStatusIcon(item.status);
                    const statusColor = getStatusColor(item.status);
                    
                    const card = document.createElement('div');
                    card.className = `card mb-2 status-card ${statusClass}`;
                    card.innerHTML = `
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-4">
                                    <strong>${item.target}</strong>
                                    <br><small class="text-muted">${item.target_type}</small>
                                </div>
                                <div class="col-md-2">
                                    <span class="badge bg-${statusColor}">
                                        ${statusIcon} ${item.status}
                                    </span>
                                </div>
                                <div class="col-md-2">
                                    延迟: ${item.latency.toFixed(1)}ms
                                </div>
                                <div class="col-md-2">
                                    丢包: ${item.packet_loss.toFixed(1)}%
                                </div>
                                <div class="col-md-2">
                                    <small class="text-muted">
                                        ${new Date(item.timestamp).toLocaleTimeString('zh-CN')}
                                    </small>
                                </div>
                            </div>
                        </div>
                    `;
                    statusList.appendChild(card);
                });
            }
            
            function updateAlertList(alerts) {
                const alertList = document.getElementById('alertList');
                alertList.innerHTML = '';
                
                if (alerts.length === 0) {
                    alertList.innerHTML = '<p class="text-center">暂无告警</p>';
                    return;
                }
                
                alerts.forEach(alert => {
                    const severityColor = alert.severity === 'HIGH' ? 'danger' : 'warning';
                    const card = document.createElement('div');
                    card.className = `card mb-2 bg-light`;
                    card.innerHTML = `
                        <div class="card-body">
                            <div class="d-flex justify-content-between">
                                <span class="badge bg-${severityColor}">${alert.severity}</span>
                                <small class="text-muted">
                                    ${new Date(alert.timestamp).toLocaleTimeString('zh-CN')}
                                </small>
                            </div>
                            <p class="mb-1"><strong>${alert.target}</strong></p>
                            <p class="mb-0 small">${alert.message}</p>
                        </div>
                    `;
                    alertList.appendChild(card);
                });
            }
            
            function getStatusIcon(status) {
                switch(status) {
                    case 'operational': return '✓';
                    case 'degraded': return '⚠';
                    case 'down': return '✗';
                    default: return '?';
                }
            }
            
            function getStatusColor(status) {
                switch(status) {
                    case 'operational': return 'success';
                    case 'degraded': return 'warning';
                    case 'down': return 'danger';
                    default: return 'secondary';
                }
            }
        </script>
    </body>
    </html>
    """

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点，用于实时数据推送"""
    await manager.connect(websocket)
    try:
        while True:
            # 获取最新数据
            summary = monitor.get_status_summary()
            alerts = monitor.get_recent_alerts()
            
            # 计算总数
            total = sum(sum(counts.values()) for counts in summary.values())
            operational = sum(counts['operational'] for counts in summary.values())
            degraded = sum(counts['degraded'] for counts in summary.values())
            down = sum(counts['down'] for counts in summary.values())
            
            # 获取详细状态
            status_data = get_recent_status()
            
            # 发送数据
            data = {
                'summary': {
                    'total': total,
                    'operational': operational,
                    'degraded': degraded,
                    'down': down
                },
                'status': status_data,
                'alerts': alerts
            }
            
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(30)  # 每30秒更新一次
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def get_recent_status() -> List[Dict]:
    """获取最近的网络状态"""
    conn = sqlite3.connect(monitor.db_path)
    cursor = conn.cursor()
    
    # 获取最近10分钟的状态
    ten_minutes_ago = datetime.now() - timedelta(minutes=10)
    
    cursor.execute('''
        SELECT timestamp, target, target_type, latency, packet_loss, status
        FROM network_status 
        WHERE timestamp > ? 
        ORDER BY timestamp DESC
        LIMIT 50
    ''', (ten_minutes_ago,))
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'timestamp': row[0],
            'target': row[1],
            'target_type': row[2],
            'latency': row[3],
            'packet_loss': row[4],
            'status': row[5]
        })
        
    conn.close()
    return results

@app.get("/api/status")
async def get_status():
    """API端点：获取网络状态"""
    summary = monitor.get_status_summary()
    alerts = monitor.get_recent_alerts()
    status_data = get_recent_status()
    
    return {
        'summary': summary,
        'alerts': alerts,
        'status': status_data,
        'timestamp': datetime.now().isoformat()
    }

@app.get("/api/alerts")
async def get_alerts(hours: int = 24):
    """API端点：获取告警"""
    return monitor.get_recent_alerts(hours)

@app.post("/api/run-monitoring")
async def run_monitoring():
    """API端点：手动运行监控"""
    try:
        results = await monitor.run_monitoring_cycle()
        return {
            'success': True,
            'message': f'监控完成，测试了 {len(results)} 个端点',
            'results_count': len(results)
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'监控失败: {str(e)}'
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 