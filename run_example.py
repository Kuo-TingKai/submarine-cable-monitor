#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Network Monitoring System Demo Script
Demonstrate how to use various features
"""

import asyncio
import json
import yaml
from datetime import datetime
from network_monitor import NetworkMonitor
from route_analyzer import RouteAnalyzer
from alert_system import AlertSystem

async def demo_network_monitoring():
    """Demonstrate network monitoring functionality"""
    print("=== Network Monitoring Demo ===")
    
    monitor = NetworkMonitor()
    
    # Run single monitoring cycle
    print("Running network monitoring...")
    results = await monitor.run_monitoring_cycle()
    
    print(f"Monitoring complete, tested {len(results)} endpoints")
    
    # Display result summary
    summary = monitor.get_status_summary()
    print("\nStatus Summary:")
    for target_type, counts in summary.items():
        print(f"  {target_type}: Operational={counts['operational']}, "
              f"Degraded={counts['degraded']}, Down={counts['down']}")
              
    # Display recent alerts
    alerts = monitor.get_recent_alerts()
    if alerts:
        print(f"\nRecent Alerts ({len(alerts)}):")
        for alert in alerts[:3]:
            print(f"  - {alert['timestamp']}: {alert['message']}")
    else:
        print("\nNo alerts")

async def demo_route_analysis():
    """Demonstrate route analysis functionality"""
    print("\n=== Route Analysis Demo ===")
    
    async with RouteAnalyzer() as analyzer:
        # Analyze submarine cable endpoints
        targets = [
            "203.208.60.1",  # C2C Hong Kong
            "202.12.27.1",   # EAC1 Hong Kong
            "8.8.8.8"        # Google DNS
        ]
        
        for target in targets:
            print(f"\nAnalyzing target: {target}")
            try:
                analysis = await analyzer.analyze_network_path(target)
                
                print(f"  Hops: {analysis['summary']['total_hops']}")
                print(f"  Average latency: {analysis['summary']['avg_latency']:.1f}ms")
                
                if analysis['summary']['as_path']:
                    print(f"  AS Path: {' -> '.join(analysis['summary']['as_path'])}")
                    
                if analysis['summary']['bottlenecks']:
                    print("  Bottleneck nodes:")
                    for bottleneck in analysis['summary']['bottlenecks'][:3]:
                        print(f"    Hop {bottleneck['hop']}: "
                              f"{bottleneck['hostname']} ({bottleneck['latency']:.1f}ms)")
                              
            except Exception as e:
                print(f"  Analysis failed: {e}")
                print(f"  Note: This may be due to network restrictions or firewall settings")
                print(f"  Traceroute and BGP queries may be blocked in some environments")

async def demo_alert_system():
    """Demonstrate alert system functionality"""
    print("\n=== Alert System Demo ===")
    
    alert_system = AlertSystem()
    
    # Simulate different network statuses
    test_cases = [
        {
            'target': '203.208.60.1',
            'target_type': 'cable',
            'packet_loss': 5.0,
            'latency': 50.0
        },
        {
            'target': '72.52.94.1',
            'target_type': 'isp',
            'packet_loss': 25.0,
            'latency': 200.0
        },
        {
            'target': '8.8.8.8',
            'target_type': 'cloud',
            'packet_loss': 100.0,
            'latency': float('inf')
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['target']} "
              f"(Packet Loss: {test_case['packet_loss']}%)")
              
        alerts = alert_system.check_alert_conditions(test_case)
        
        if alerts:
            for alert in alerts:
                print(f"  Alert triggered: {alert.message} (Level: {alert.severity})")
                # Save alert
                alert_id = alert_system.save_alert(alert)
                print(f"  Alert saved, ID: {alert_id}")
        else:
            print("  No alerts triggered")
            
    # Display alert statistics
    stats = alert_system.get_alert_statistics()
    print(f"\nAlert Statistics:")
    print(f"  Total alerts: {stats['total_alerts']}")
    print(f"  Active alerts: {stats['active_alerts']}")
    print(f"  Resolved: {stats['resolved_alerts']}")

async def demo_integrated_system():
    """Demonstrate integrated system functionality"""
    print("\n=== Integrated System Demo ===")
    
    monitor = NetworkMonitor()
    alert_system = AlertSystem()
    
    print("Running complete monitoring cycle...")
    
    # Run monitoring
    results = await monitor.run_monitoring_cycle()
    
    # Process alerts
    triggered_alerts = []
    for result in results:
        alerts = alert_system.check_alert_conditions({
            'target': result.target,
            'target_type': result.target_type,
            'packet_loss': result.packet_loss,
            'latency': result.latency
        })
        
        for alert in alerts:
            alert_id = alert_system.save_alert(alert)
            triggered_alerts.append(alert)
            print(f"Alert: {alert.message}")
            
    # Generate report
    report = {
        'timestamp': datetime.now().isoformat(),
        'monitoring_results': {
            'total_endpoints': len(results),
            'operational': len([r for r in results if r.status == 'operational']),
            'degraded': len([r for r in results if r.status == 'degraded']),
            'down': len([r for r in results if r.status == 'down'])
        },
        'alerts': {
            'total_triggered': len(triggered_alerts),
            'by_severity': {}
        }
    }
    
    # Count alerts by severity
    for alert in triggered_alerts:
        severity = alert.severity
        if severity not in report['alerts']['by_severity']:
            report['alerts']['by_severity'][severity] = 0
        report['alerts']['by_severity'][severity] += 1
        
    print(f"\nMonitoring Report:")
    print(json.dumps(report, indent=2, ensure_ascii=False))

def demo_configuration():
    """Demonstrate configuration functionality"""
    print("\n=== Configuration Demo ===")
    
    monitor = NetworkMonitor()
    
    print("Current Configuration:")
    config = monitor.config['network_monitoring']
    
    print(f"Monitoring interval: {config['monitoring']['ping_interval']} seconds")
    print(f"Timeout: {config['monitoring']['timeout']} seconds")
    print(f"Retry count: {config['monitoring']['retry_count']}")
    
    print(f"\nSubmarine cable systems: {len(config['submarine_cables'])}")
    for cable_name, cable_config in config['submarine_cables'].items():
        print(f"  {cable_name}: {len(cable_config['endpoints'])} endpoints")
        
    print(f"\nISPs: {len(config['isps'])}")
    for isp_name, isp_config in config['isps'].items():
        print(f"  {isp_name}: {len(isp_config['endpoints'])} endpoints")
        
    print(f"\nCloud service providers: {len(config['cloud_providers'])}")
    for provider_name, provider_config in config['cloud_providers'].items():
        print(f"  {provider_name}: {len(provider_config['regions'])} regions")

async def main():
    """Main demo function"""
    print("Network Monitoring System Feature Demo")
    print("=" * 50)
    
    try:
        # Demo various feature modules
        await demo_network_monitoring()
        await demo_route_analysis()
        await demo_alert_system()
        await demo_integrated_system()
        demo_configuration()
        
        print("\n" + "=" * 50)
        print("Demo complete!")
        print("\nUsage Instructions:")
        print("1. Start continuous monitoring: python main.py --mode monitor")
        print("2. Start Web dashboard: python main.py --mode dashboard")
        print("3. View status: python main.py --mode status")
        print("4. Route analysis: python main.py --mode analyze --targets 8.8.8.8")
        
    except Exception as e:
        print(f"Error occurred during demo: {e}")
        print("Please check if configuration file and dependencies are correctly installed")

if __name__ == "__main__":
    asyncio.run(main()) 