#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Network Monitoring System
Monitor connectivity status of submarine cable systems, ISPs, and cloud service providers
"""

import asyncio
import aiohttp
import sqlite3
import yaml
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from ping3 import ping
import threading
import queue

@dataclass
class NetworkStatus:
    """Network status data class"""
    timestamp: datetime
    target: str
    target_type: str  # cable, isp, cloud
    latency: float
    packet_loss: float
    status: str  # operational, degraded, down
    details: Dict

class NetworkMonitor:
    """Main network monitoring class"""
    
    def __init__(self, config_file: str = "config.yaml"):
        """Initialize network monitor"""
        self.config = self._load_config(config_file)
        self.db_path = self.config['network_monitoring']['database']['path']
        self._setup_logging()
        self._setup_database()
        self.monitoring_queue = queue.Queue()
        self.is_running = False
        
    def _load_config(self, config_file: str) -> Dict:
        """Load configuration file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file {config_file} not found")
            
    def _setup_logging(self):
        """Setup logging system"""
        log_config = self.config['network_monitoring']['logging']
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_config['file'], encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _setup_database(self):
        """Initialize database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create network status table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS network_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                target TEXT NOT NULL,
                target_type TEXT NOT NULL,
                latency REAL,
                packet_loss REAL,
                status TEXT NOT NULL,
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                target TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                resolved BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        self.logger.info("Database initialization complete")
        
    async def ping_target(self, target: str, timeout: int = 5) -> Tuple[float, float]:
        """Asynchronous ping target address"""
        try:
            # Use ping3 library for ping testing
            result = ping(target, timeout=timeout)
            if result is not None:
                return result * 1000, 0.0  # Convert to milliseconds, no packet loss
            else:
                return float('inf'), 100.0  # Timeout, 100% packet loss
        except Exception as e:
            self.logger.error(f"Ping {target} failed: {e}")
            return float('inf'), 100.0
            
    async def test_endpoint(self, endpoint: str, target_type: str) -> NetworkStatus:
        """Test single endpoint"""
        config = self.config['network_monitoring']['monitoring']
        timeout = config['timeout']
        retry_count = config['retry_count']
        
        latencies = []
        packet_losses = []
        
        # Multiple tests for average
        for _ in range(retry_count):
            latency, loss = await self.ping_target(endpoint, timeout)
            latencies.append(latency)
            packet_losses.append(loss)
            await asyncio.sleep(1)  # 1 second interval
            
        avg_latency = sum(latencies) / len(latencies)
        avg_packet_loss = sum(packet_losses) / len(packet_losses)
        
        # Determine status
        if avg_packet_loss >= 100:
            status = "down"
        elif avg_packet_loss >= 20:
            status = "degraded"
        else:
            status = "operational"
            
        return NetworkStatus(
            timestamp=datetime.now(),
            target=endpoint,
            target_type=target_type,
            latency=avg_latency,
            packet_loss=avg_packet_loss,
            status=status,
            details={
                "latencies": latencies,
                "packet_losses": packet_losses,
                "retry_count": retry_count
            }
        )
        
    async def monitor_submarine_cables(self) -> List[NetworkStatus]:
        """Monitor submarine cable systems"""
        cables = self.config['network_monitoring']['submarine_cables']
        results = []
        
        for cable_name, cable_config in cables.items():
            self.logger.info(f"Monitoring submarine cable system: {cable_name}")
            
            for endpoint in cable_config['endpoints']:
                status = await self.test_endpoint(endpoint, 'cable')
                results.append(status)
                
                # Save to database
                self._save_status(status)
                
                # Check if alert is needed
                if status.status != "operational":
                    self._create_alert(status, f"Submarine cable system {cable_name} status abnormal")
                    
        return results
        
    async def monitor_isps(self) -> List[NetworkStatus]:
        """Monitor ISPs"""
        isps = self.config['network_monitoring']['isps']
        results = []
        
        for isp_name, isp_config in isps.items():
            self.logger.info(f"Monitoring ISP: {isp_name}")
            
            for endpoint in isp_config['endpoints']:
                status = await self.test_endpoint(endpoint, 'isp')
                results.append(status)
                
                # Save to database
                self._save_status(status)
                
                # Check if alert is needed
                if status.status != "operational":
                    self._create_alert(status, f"ISP {isp_name} status abnormal")
                    
        return results
        
    async def monitor_cloud_providers(self) -> List[NetworkStatus]:
        """Monitor cloud service providers"""
        providers = self.config['network_monitoring']['cloud_providers']
        results = []
        
        for provider_name, provider_config in providers.items():
            self.logger.info(f"Monitoring cloud service provider: {provider_name}")
            
            for region in provider_config['regions']:
                status = await self.test_endpoint(region['endpoint'], 'cloud')
                results.append(status)
                
                # Save to database
                self._save_status(status)
                
                # Check if alert is needed
                if status.status != "operational":
                    self._create_alert(status, f"Cloud service {provider_name} {region['name']} status abnormal")
                    
        return results
        
    def _save_status(self, status: NetworkStatus):
        """Save status to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO network_status 
            (timestamp, target, target_type, latency, packet_loss, status, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            status.timestamp,
            status.target,
            status.target_type,
            status.latency,
            status.packet_loss,
            status.status,
            json.dumps(status.details)
        ))
        
        conn.commit()
        conn.close()
        
    def _create_alert(self, status: NetworkStatus, message: str):
        """Create alert"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        severity = "HIGH" if status.status == "down" else "MEDIUM"
        
        cursor.execute('''
            INSERT INTO alerts 
            (timestamp, target, alert_type, message, severity)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            status.timestamp,
            status.target,
            status.status,
            message,
            severity
        ))
        
        conn.commit()
        conn.close()
        
        self.logger.warning(f"Alert: {message} - {status.target} ({status.status})")
        
    async def run_monitoring_cycle(self):
        """Run a complete monitoring cycle"""
        self.logger.info("Starting network monitoring cycle")
        
        # Execute all monitoring tasks in parallel
        tasks = [
            self.monitor_submarine_cables(),
            self.monitor_isps(),
            self.monitor_cloud_providers()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        all_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Monitoring task exception: {result}")
            else:
                all_results.extend(result)
                
        self.logger.info(f"Monitoring cycle complete, tested {len(all_results)} endpoints")
        return all_results
        
    async def start_monitoring(self):
        """Start continuous monitoring"""
        self.is_running = True
        interval = self.config['network_monitoring']['monitoring']['ping_interval']
        
        self.logger.info(f"Starting continuous monitoring, interval: {interval} seconds")
        
        while self.is_running:
            try:
                await self.run_monitoring_cycle()
                await asyncio.sleep(interval)
            except Exception as e:
                self.logger.error(f"Monitoring loop exception: {e}")
                await asyncio.sleep(10)  # Wait 10 seconds after exception
                
    def stop_monitoring(self):
        """Stop monitoring"""
        self.is_running = False
        self.logger.info("Monitoring stopped")
        
    def get_status_summary(self) -> Dict:
        """Get status summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get status from last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        cursor.execute('''
            SELECT target_type, status, COUNT(*) 
            FROM network_status 
            WHERE timestamp > ? 
            GROUP BY target_type, status
        ''', (one_hour_ago,))
        
        results = cursor.fetchall()
        
        summary = {
            'cable': {'operational': 0, 'degraded': 0, 'down': 0},
            'isp': {'operational': 0, 'degraded': 0, 'down': 0},
            'cloud': {'operational': 0, 'degraded': 0, 'down': 0}
        }
        
        for target_type, status, count in results:
            if target_type in summary:
                summary[target_type][status] = count
                
        conn.close()
        return summary
        
    def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """Get recent alerts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(hours=hours)
        
        cursor.execute('''
            SELECT timestamp, target, alert_type, message, severity
            FROM alerts 
            WHERE timestamp > ? AND resolved = FALSE
            ORDER BY timestamp DESC
        ''', (since,))
        
        alerts = []
        for row in cursor.fetchall():
            alerts.append({
                'timestamp': row[0],
                'target': row[1],
                'alert_type': row[2],
                'message': row[3],
                'severity': row[4]
            })
            
        conn.close()
        return alerts

if __name__ == "__main__":
    # Example usage
    async def main():
        monitor = NetworkMonitor()
        
        # Run single monitoring cycle
        results = await monitor.run_monitoring_cycle()
        
        # Print summary
        summary = monitor.get_status_summary()
        print("Status Summary:")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        
        # Print alerts
        alerts = monitor.get_recent_alerts()
        if alerts:
            print("\nRecent Alerts:")
            for alert in alerts:
                print(f"- {alert['timestamp']}: {alert['message']}")
        
    asyncio.run(main()) 