#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
告警系统
支持多种告警方式和通知渠道
"""

import asyncio
import smtplib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import sqlite3

@dataclass
class AlertRule:
    """告警规则"""
    name: str
    condition: str  # threshold, percentage, consecutive_failures
    threshold: float
    target_type: str  # cable, isp, cloud, all
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    enabled: bool = True

@dataclass
class Alert:
    """告警信息"""
    id: Optional[int]
    timestamp: datetime
    rule_name: str
    target: str
    target_type: str
    severity: str
    message: str
    details: Dict
    resolved: bool = False
    resolved_at: Optional[datetime] = None

class AlertSystem:
    """告警系统主类"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config = self._load_config(config_file)
        self.logger = logging.getLogger(__name__)
        self.db_path = self.config['network_monitoring']['database']['path']
        self._setup_alert_rules()
        
    def _load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件 {config_file} 不存在")
            
    def _setup_alert_rules(self):
        """设置默认告警规则"""
        self.alert_rules = [
            AlertRule(
                name="高丢包率告警",
                condition="threshold",
                threshold=20.0,
                target_type="all",
                severity="MEDIUM"
            ),
            AlertRule(
                name="完全中断告警",
                condition="threshold",
                threshold=100.0,
                target_type="all",
                severity="HIGH"
            ),
            AlertRule(
                name="海缆系统异常",
                condition="threshold",
                threshold=10.0,
                target_type="cable",
                severity="HIGH"
            ),
            AlertRule(
                name="ISP连接异常",
                condition="threshold",
                threshold=15.0,
                target_type="isp",
                severity="MEDIUM"
            ),
            AlertRule(
                name="云服务异常",
                condition="threshold",
                threshold=25.0,
                target_type="cloud",
                severity="MEDIUM"
            )
        ]
        
    def check_alert_conditions(self, status_data: Dict) -> List[Alert]:
        """检查告警条件"""
        alerts = []
        
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
                
            # 根据目标类型过滤
            if rule.target_type != "all" and status_data['target_type'] != rule.target_type:
                continue
                
            # 检查条件
            if rule.condition == "threshold":
                if status_data['packet_loss'] >= rule.threshold:
                    alert = Alert(
                        id=None,
                        timestamp=datetime.now(),
                        rule_name=rule.name,
                        target=status_data['target'],
                        target_type=status_data['target_type'],
                        severity=rule.severity,
                        message=f"{rule.name}: {status_data['target']} 丢包率 {status_data['packet_loss']:.1f}%",
                        details={
                            'packet_loss': status_data['packet_loss'],
                            'latency': status_data['latency'],
                            'threshold': rule.threshold
                        }
                    )
                    alerts.append(alert)
                    
        return alerts
        
    def save_alert(self, alert: Alert) -> int:
        """保存告警到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO alerts 
            (timestamp, target, alert_type, message, severity, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            alert.timestamp,
            alert.target,
            alert.rule_name,
            alert.message,
            alert.severity,
            json.dumps(alert.details)
        ))
        
        alert_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return alert_id
        
    def resolve_alert(self, alert_id: int):
        """解决告警"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE alerts 
            SET resolved = TRUE, resolved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (alert_id,))
        
        conn.commit()
        conn.close()
        
    async def send_email_alert(self, alert: Alert):
        """发送邮件告警"""
        if 'email' not in self.config['network_monitoring']:
            return
            
        email_config = self.config['network_monitoring']['email']
        
        try:
            msg = MIMEMultipart()
            msg['From'] = email_config['from']
            msg['To'] = email_config['to']
            msg['Subject'] = f"[网络监控] {alert.severity} 级别告警"
            
            body = f"""
            告警时间: {alert.timestamp}
            告警规则: {alert.rule_name}
            目标地址: {alert.target}
            目标类型: {alert.target_type}
            严重程度: {alert.severity}
            告警消息: {alert.message}
            
            详细信息:
            {json.dumps(alert.details, indent=2, ensure_ascii=False)}
            """
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                if email_config.get('use_tls', True):
                    server.starttls()
                server.login(email_config['username'], email_config['password'])
                server.send_message(msg)
                
            self.logger.info(f"邮件告警已发送: {alert.message}")
            
        except Exception as e:
            self.logger.error(f"发送邮件告警失败: {e}")
            
    async def send_webhook_alert(self, alert: Alert):
        """发送Webhook告警"""
        if 'webhook' not in self.config['network_monitoring']:
            return
            
        webhook_config = self.config['network_monitoring']['webhook']
        
        try:
            payload = {
                'timestamp': alert.timestamp.isoformat(),
                'rule_name': alert.rule_name,
                'target': alert.target,
                'target_type': alert.target_type,
                'severity': alert.severity,
                'message': alert.message,
                'details': alert.details
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_config['url'],
                    json=payload,
                    headers=webhook_config.get('headers', {}),
                    timeout=10
                ) as response:
                    if response.status == 200:
                        self.logger.info(f"Webhook告警已发送: {alert.message}")
                    else:
                        self.logger.error(f"Webhook告警发送失败: {response.status}")
                        
        except Exception as e:
            self.logger.error(f"发送Webhook告警失败: {e}")
            
    async def send_slack_alert(self, alert: Alert):
        """发送Slack告警"""
        if 'slack' not in self.config['network_monitoring']:
            return
            
        slack_config = self.config['network_monitoring']['slack']
        
        try:
            # 根据严重程度选择颜色
            color_map = {
                'LOW': '#36a64f',
                'MEDIUM': '#ff9500',
                'HIGH': '#ff0000',
                'CRITICAL': '#8b0000'
            }
            
            payload = {
                'attachments': [{
                    'color': color_map.get(alert.severity, '#cccccc'),
                    'title': f"网络监控告警 - {alert.severity}",
                    'text': alert.message,
                    'fields': [
                        {
                            'title': '目标地址',
                            'value': alert.target,
                            'short': True
                        },
                        {
                            'title': '目标类型',
                            'value': alert.target_type,
                            'short': True
                        },
                        {
                            'title': '告警规则',
                            'value': alert.rule_name,
                            'short': True
                        },
                        {
                            'title': '时间',
                            'value': alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            'short': True
                        }
                    ],
                    'footer': '网络监控系统'
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    slack_config['webhook_url'],
                    json=payload,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        self.logger.info(f"Slack告警已发送: {alert.message}")
                    else:
                        self.logger.error(f"Slack告警发送失败: {response.status}")
                        
        except Exception as e:
            self.logger.error(f"发送Slack告警失败: {e}")
            
    async def send_alert_notifications(self, alert: Alert):
        """发送所有告警通知"""
        tasks = []
        
        # 根据严重程度决定发送哪些通知
        if alert.severity in ['HIGH', 'CRITICAL']:
            tasks.extend([
                self.send_email_alert(alert),
                self.send_webhook_alert(alert),
                self.send_slack_alert(alert)
            ])
        elif alert.severity == 'MEDIUM':
            tasks.extend([
                self.send_webhook_alert(alert),
                self.send_slack_alert(alert)
            ])
        else:  # LOW
            tasks.append(self.send_slack_alert(alert))
            
        # 并行发送通知
        await asyncio.gather(*tasks, return_exceptions=True)
        
    def get_active_alerts(self, hours: int = 24) -> List[Alert]:
        """获取活跃告警"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(hours=hours)
        
        cursor.execute('''
            SELECT id, timestamp, target, alert_type, message, severity, details
            FROM alerts 
            WHERE timestamp > ? AND resolved = FALSE
            ORDER BY timestamp DESC
        ''', (since,))
        
        alerts = []
        for row in cursor.fetchall():
            alert = Alert(
                id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                rule_name=row[3],
                target=row[2],
                target_type='',  # 需要从details中解析
                severity=row[5],
                message=row[4],
                details=json.loads(row[6]) if row[6] else {}
            )
            alerts.append(alert)
            
        conn.close()
        return alerts
        
    def get_alert_statistics(self, hours: int = 24) -> Dict:
        """获取告警统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(hours=hours)
        
        # 按严重程度统计
        cursor.execute('''
            SELECT severity, COUNT(*) 
            FROM alerts 
            WHERE timestamp > ? 
            GROUP BY severity
        ''', (since,))
        
        severity_stats = dict(cursor.fetchall())
        
        # 按目标类型统计
        cursor.execute('''
            SELECT target_type, COUNT(*) 
            FROM alerts 
            WHERE timestamp > ? 
            GROUP BY target_type
        ''', (since,))
        
        type_stats = dict(cursor.fetchall())
        
        # 已解决的告警数量
        cursor.execute('''
            SELECT COUNT(*) 
            FROM alerts 
            WHERE timestamp > ? AND resolved = TRUE
        ''', (since,))
        
        resolved_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_alerts': sum(severity_stats.values()),
            'resolved_alerts': resolved_count,
            'active_alerts': sum(severity_stats.values()) - resolved_count,
            'severity_distribution': severity_stats,
            'type_distribution': type_stats
        }
        
    def add_alert_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.alert_rules.append(rule)
        
    def remove_alert_rule(self, rule_name: str):
        """删除告警规则"""
        self.alert_rules = [rule for rule in self.alert_rules if rule.name != rule_name]
        
    def update_alert_rule(self, rule_name: str, **kwargs):
        """更新告警规则"""
        for rule in self.alert_rules:
            if rule.name == rule_name:
                for key, value in kwargs.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                break

async def main():
    """示例用法"""
    alert_system = AlertSystem()
    
    # 模拟网络状态数据
    test_status = {
        'target': '203.208.60.1',
        'target_type': 'cable',
        'packet_loss': 25.0,
        'latency': 150.0
    }
    
    # 检查告警条件
    alerts = alert_system.check_alert_conditions(test_status)
    
    if alerts:
        for alert in alerts:
            # 保存告警
            alert_id = alert_system.save_alert(alert)
            print(f"告警已保存，ID: {alert_id}")
            
            # 发送通知
            await alert_system.send_alert_notifications(alert)
            
    # 获取告警统计
    stats = alert_system.get_alert_statistics()
    print("告警统计:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    import yaml
    import aiohttp
    asyncio.run(main()) 