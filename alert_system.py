#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alert System
Support multiple alert methods and notification channels
"""

import asyncio
import smtplib
import json
import logging
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import sqlite3

@dataclass
class AlertRule:
    """Alert rule"""
    name: str
    condition: str  # threshold, percentage, consecutive_failures
    threshold: float
    target_type: str  # cable, isp, cloud, all
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    enabled: bool = True

@dataclass
class Alert:
    """Alert information"""
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
    """Main alert system class"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config = self._load_config(config_file)
        self.logger = logging.getLogger(__name__)
        self.db_path = self.config['network_monitoring']['database']['path']
        self._setup_alert_rules()
        
    def _load_config(self, config_file: str) -> Dict:
        """Load configuration file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file {config_file} does not exist")
            
    def _setup_alert_rules(self):
        """Set default alert rules"""
        self.alert_rules = [
            AlertRule(
                name="High Packet Loss Alert",
                condition="threshold",
                threshold=20.0,
                target_type="all",
                severity="MEDIUM"
            ),
            AlertRule(
                name="Complete Outage Alert",
                condition="threshold",
                threshold=100.0,
                target_type="all",
                severity="HIGH"
            ),
            AlertRule(
                name="Submarine Cable System Anomaly",
                condition="threshold",
                threshold=10.0,
                target_type="cable",
                severity="HIGH"
            ),
            AlertRule(
                name="ISP Connection Anomaly",
                condition="threshold",
                threshold=15.0,
                target_type="isp",
                severity="MEDIUM"
            ),
            AlertRule(
                name="Cloud Service Anomaly",
                condition="threshold",
                threshold=25.0,
                target_type="cloud",
                severity="MEDIUM"
            )
        ]
        
    def check_alert_conditions(self, status_data: Dict) -> List[Alert]:
        """Check alert conditions"""
        alerts = []
        
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
                
            # Filter by target type
            if rule.target_type != "all" and status_data['target_type'] != rule.target_type:
                continue
                
            # Check conditions
            if rule.condition == "threshold":
                if status_data['packet_loss'] >= rule.threshold:
                    alert = Alert(
                        id=None,
                        timestamp=datetime.now(),
                        rule_name=rule.name,
                        target=status_data['target'],
                        target_type=status_data['target_type'],
                        severity=rule.severity,
                        message=f"{rule.name}: {status_data['target']} packet loss {status_data['packet_loss']:.1f}%",
                        details={
                            'packet_loss': status_data['packet_loss'],
                            'latency': status_data['latency'],
                            'threshold': rule.threshold
                        }
                    )
                    alerts.append(alert)
                    
        return alerts
        
    def save_alert(self, alert: Alert) -> int:
        """Save alert to database"""
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
        """Resolve alert"""
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
        """Send email alert"""
        if 'email' not in self.config['network_monitoring']:
            return
            
        email_config = self.config['network_monitoring']['email']
        
        try:
            msg = MIMEMultipart()
            msg['From'] = email_config['from']
            msg['To'] = email_config['to']
            msg['Subject'] = f"[Network Monitoring] {alert.severity} Level Alert"
            
            body = f"""
            Alert Time: {alert.timestamp}
            Alert Rule: {alert.rule_name}
            Target Address: {alert.target}
            Target Type: {alert.target_type}
            Severity: {alert.severity}
            Alert Message: {alert.message}
            
            Details:
            {json.dumps(alert.details, indent=2, ensure_ascii=False)}
            """
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                if email_config.get('use_tls', True):
                    server.starttls()
                server.login(email_config['username'], email_config['password'])
                server.send_message(msg)
                
            self.logger.info(f"Email alert sent: {alert.message}")
            
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")
            
    async def send_webhook_alert(self, alert: Alert):
        """Send Webhook alert"""
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
                        self.logger.info(f"Webhook alert sent: {alert.message}")
                    else:
                        self.logger.error(f"Webhook alert failed to send: {response.status}")
                        
        except Exception as e:
            self.logger.error(f"Failed to send Webhook alert: {e}")
            
    async def send_slack_alert(self, alert: Alert):
        """Send Slack alert"""
        if 'slack' not in self.config['network_monitoring']:
            return
            
        slack_config = self.config['network_monitoring']['slack']
        
        try:
            # Choose color based on severity
            color_map = {
                'LOW': '#36a64f',
                'MEDIUM': '#ff9500',
                'HIGH': '#ff0000',
                'CRITICAL': '#8b0000'
            }
            
            payload = {
                'attachments': [{
                    'color': color_map.get(alert.severity, '#cccccc'),
                    'title': f"Network Monitoring Alert - {alert.severity}",
                    'text': alert.message,
                    'fields': [
                        {
                            'title': 'Target Address',
                            'value': alert.target,
                            'short': True
                        },
                        {
                            'title': 'Target Type',
                            'value': alert.target_type,
                            'short': True
                        },
                        {
                            'title': 'Alert Rule',
                            'value': alert.rule_name,
                            'short': True
                        },
                        {
                            'title': 'Time',
                            'value': alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            'short': True
                        }
                    ],
                    'footer': 'Network Monitoring System'
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    slack_config['webhook_url'],
                    json=payload,
                    timeout=10
                ) as response:
                    if response.status == 200:
                        self.logger.info(f"Slack alert sent: {alert.message}")
                    else:
                        self.logger.error(f"Slack alert failed to send: {response.status}")
                        
        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {e}")
            
    async def send_alert_notifications(self, alert: Alert):
        """Send all alert notifications"""
        tasks = []
        
        # Decide which notifications to send based on severity
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
            
        # Send notifications in parallel
        await asyncio.gather(*tasks, return_exceptions=True)
        
    def get_active_alerts(self, hours: int = 24) -> List[Alert]:
        """Get active alerts"""
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
                target_type='',  # Need to parse from details
                severity=row[5],
                message=row[4],
                details=json.loads(row[6]) if row[6] else {}
            )
            alerts.append(alert)
            
        conn.close()
        return alerts
        
    def get_alert_statistics(self, hours: int = 24) -> Dict:
        """Get alert statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(hours=hours)
        
        # Group by severity
        cursor.execute('''
            SELECT severity, COUNT(*) 
            FROM alerts 
            WHERE timestamp > ? 
            GROUP BY severity
        ''', (since,))
        
        severity_stats = dict(cursor.fetchall())
        
        # Group by target type
        cursor.execute('''
            SELECT target_type, COUNT(*) 
            FROM alerts 
            WHERE timestamp > ? 
            GROUP BY target_type
        ''', (since,))
        
        type_stats = dict(cursor.fetchall())
        
        # Count resolved alerts
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
        """Add alert rule"""
        self.alert_rules.append(rule)
        
    def remove_alert_rule(self, rule_name: str):
        """Remove alert rule"""
        self.alert_rules = [rule for rule in self.alert_rules if rule.name != rule_name]
        
    def update_alert_rule(self, rule_name: str, **kwargs):
        """Update alert rule"""
        for rule in self.alert_rules:
            if rule.name == rule_name:
                for key, value in kwargs.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                break

async def main():
    """Example usage"""
    alert_system = AlertSystem()
    
    # Simulate network status data
    test_status = {
        'target': '203.208.60.1',
        'target_type': 'cable',
        'packet_loss': 25.0,
        'latency': 150.0
    }
    
    # Check alert conditions
    alerts = alert_system.check_alert_conditions(test_status)
    
    if alerts:
        for alert in alerts:
            # Save alert
            alert_id = alert_system.save_alert(alert)
            print(f"Alert saved, ID: {alert_id}")
            
            # Send notifications
            await alert_system.send_alert_notifications(alert)
            
    # Get alert statistics
    stats = alert_system.get_alert_statistics()
    print("Alert Statistics:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    import yaml
    import aiohttp
    asyncio.run(main()) 