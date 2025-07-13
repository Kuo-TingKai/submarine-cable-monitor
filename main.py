#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Network Monitoring System Main Program
Integrate all functional modules
"""

import asyncio
import argparse
import signal
import sys
import logging
from datetime import datetime
from typing import Dict, List

from network_monitor import NetworkMonitor
from route_analyzer import RouteAnalyzer
from alert_system import AlertSystem
from web_dashboard import app as dashboard_app
import uvicorn

class NetworkMonitoringSystem:
    """Main class for the network monitoring system"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.monitor = NetworkMonitor(config_file)
        self.alert_system = AlertSystem(config_file)
        self.is_running = False
        
        # Set up signal handling
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Signal handler"""
        print(f"\nReceived signal {signum}, stopping the monitoring system...")
        self.stop()
        
    async def start_monitoring(self):
        """Start monitoring"""
        self.is_running = True
        print("Starting the network monitoring system...")
        print(f"Monitoring interval: {self.monitor.config['network_monitoring']['monitoring']['ping_interval']} seconds")
        
        try:
            await self.monitor.start_monitoring()
        except KeyboardInterrupt:
            print("\nUser interrupted, stopping...")
        finally:
            self.stop()
            
    def stop(self):
        """Stop monitoring"""
        if self.is_running:
            self.is_running = False
            self.monitor.stop_monitoring()
            print("Monitoring system stopped")
            
    async def run_single_cycle(self):
        """Run a single monitoring cycle"""
        print("Running a single monitoring cycle...")
        results = await self.monitor.run_monitoring_cycle()
        
        # Process alerts
        for result in results:
            alerts = self.alert_system.check_alert_conditions({
                'target': result.target,
                'target_type': result.target_type,
                'packet_loss': result.packet_loss,
                'latency': result.latency
            })
            
            for alert in alerts:
                alert_id = self.alert_system.save_alert(alert)
                await self.alert_system.send_alert_notifications(alert)
                print(f"Alert triggered: {alert.message}")
                
        return results
        
    async def analyze_routes(self, targets: List[str]):
        """Analyze routes"""
        print("Starting route analysis...")
        
        async with RouteAnalyzer() as analyzer:
            for target in targets:
                print(f"\nAnalyzing target: {target}")
                analysis = await analyzer.analyze_network_path(target)
                
                print(f"  Hops: {analysis['summary']['total_hops']}")
                print(f"  Average latency: {analysis['summary']['avg_latency']:.1f}ms")
                print(f"  AS path: {' -> '.join(analysis['summary']['as_path'])}")
                
                if analysis['summary']['bottlenecks']:
                    print("  Bottleneck nodes:")
                    for bottleneck in analysis['summary']['bottlenecks']:
                        print(f"    Hop {bottleneck['hop']}: {bottleneck['hostname']} "
                              f"({bottleneck['latency']:.1f}ms)")
                          
    def show_status(self):
        """Display status summary"""
        summary = self.monitor.get_status_summary()
        alerts = self.alert_system.get_active_alerts()
        
        print("\n=== Network Status Summary ===")
        for target_type, counts in summary.items():
            print(f"\n{target_type.upper()}:")
            print(f"  Operational: {counts['operational']}")
            print(f"  Degraded: {counts['degraded']}")
            print(f"  Down: {counts['down']}")
            
        print(f"\nActive alerts: {len(alerts)}")
        for alert in alerts[:5]:  # Display first 5 alerts
            print(f"  - {alert.message}")
            
    def show_statistics(self, hours: int = 24):
        """Display statistics"""
        stats = self.alert_system.get_alert_statistics(hours)
        
        print(f"\n=== Alert Statistics (last {hours} hours) ===")
        print(f"Total alerts: {stats['total_alerts']}")
        print(f"Resolved: {stats['resolved_alerts']}")
        print(f"Active alerts: {stats['active_alerts']}")
        
        print("\nSeverity distribution:")
        for severity, count in stats['severity_distribution'].items():
            print(f"  {severity}: {count}")
            
        print("\nType distribution:")
        for target_type, count in stats['type_distribution'].items():
            print(f"  {target_type}: {count}")
            
    async def start_dashboard(self, host: str = "0.0.0.0", port: int = 8000):
        """Start Web dashboard"""
        print(f"Starting Web dashboard: http://{host}:{port}")
        config = uvicorn.Config(dashboard_app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Network monitoring system")
    parser.add_argument("--config", "-c", default="config.yaml", 
                       help="Configuration file path")
    parser.add_argument("--mode", "-m", choices=["monitor", "single", "analyze", 
                                                "status", "stats", "dashboard"],
                       default="monitor", help="Run mode")
    parser.add_argument("--targets", "-t", nargs="+", 
                       help="List of target addresses for analysis")
    parser.add_argument("--hours", type=int, default=24,
                       help="Statistical time range (hours)")
    parser.add_argument("--host", default="0.0.0.0",
                       help="Web dashboard host address")
    parser.add_argument("--port", type=int, default=8000,
                       help="Web dashboard port")
    
    args = parser.parse_args()
    
    # Create monitoring system
    system = NetworkMonitoringSystem(args.config)
    
    async def run():
        """Run main program"""
        try:
            if args.mode == "monitor":
                await system.start_monitoring()
            elif args.mode == "single":
                await system.run_single_cycle()
            elif args.mode == "analyze":
                if not args.targets:
                    print("Error: Target addresses are required for analysis mode")
                    sys.exit(1)
                await system.analyze_routes(args.targets)
            elif args.mode == "status":
                system.show_status()
            elif args.mode == "stats":
                system.show_statistics(args.hours)
            elif args.mode == "dashboard":
                await system.start_dashboard(args.host, args.port)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
            
    # Run program
    asyncio.run(run())

if __name__ == "__main__":
    main() 