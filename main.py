#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络监控系统主程序
整合所有功能模块
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
    """网络监控系统主类"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.monitor = NetworkMonitor(config_file)
        self.alert_system = AlertSystem(config_file)
        self.is_running = False
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        print(f"\n收到信号 {signum}，正在停止监控系统...")
        self.stop()
        
    async def start_monitoring(self):
        """开始监控"""
        self.is_running = True
        print("启动网络监控系统...")
        print(f"监控间隔: {self.monitor.config['network_monitoring']['monitoring']['ping_interval']}秒")
        
        try:
            await self.monitor.start_monitoring()
        except KeyboardInterrupt:
            print("\n用户中断，正在停止...")
        finally:
            self.stop()
            
    def stop(self):
        """停止监控"""
        if self.is_running:
            self.is_running = False
            self.monitor.stop_monitoring()
            print("监控系统已停止")
            
    async def run_single_cycle(self):
        """运行单次监控周期"""
        print("运行单次监控周期...")
        results = await self.monitor.run_monitoring_cycle()
        
        # 处理告警
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
                print(f"告警已触发: {alert.message}")
                
        return results
        
    async def analyze_routes(self, targets: List[str]):
        """分析路由"""
        print("开始路由分析...")
        
        async with RouteAnalyzer() as analyzer:
            for target in targets:
                print(f"\n分析目标: {target}")
                analysis = await analyzer.analyze_network_path(target)
                
                print(f"  跳数: {analysis['summary']['total_hops']}")
                print(f"  平均延迟: {analysis['summary']['avg_latency']:.1f}ms")
                print(f"  AS路径: {' -> '.join(analysis['summary']['as_path'])}")
                
                if analysis['summary']['bottlenecks']:
                    print("  瓶颈节点:")
                    for bottleneck in analysis['summary']['bottlenecks']:
                        print(f"    跳 {bottleneck['hop']}: {bottleneck['hostname']} "
                              f"({bottleneck['latency']:.1f}ms)")
                          
    def show_status(self):
        """显示状态摘要"""
        summary = self.monitor.get_status_summary()
        alerts = self.alert_system.get_active_alerts()
        
        print("\n=== 网络状态摘要 ===")
        for target_type, counts in summary.items():
            print(f"\n{target_type.upper()}:")
            print(f"  正常运行: {counts['operational']}")
            print(f"  性能下降: {counts['degraded']}")
            print(f"  完全中断: {counts['down']}")
            
        print(f"\n活跃告警: {len(alerts)}")
        for alert in alerts[:5]:  # 显示前5个告警
            print(f"  - {alert.message}")
            
    def show_statistics(self, hours: int = 24):
        """显示统计信息"""
        stats = self.alert_system.get_alert_statistics(hours)
        
        print(f"\n=== 告警统计 (最近{hours}小时) ===")
        print(f"总告警数: {stats['total_alerts']}")
        print(f"已解决: {stats['resolved_alerts']}")
        print(f"活跃告警: {stats['active_alerts']}")
        
        print("\n按严重程度分布:")
        for severity, count in stats['severity_distribution'].items():
            print(f"  {severity}: {count}")
            
        print("\n按类型分布:")
        for target_type, count in stats['type_distribution'].items():
            print(f"  {target_type}: {count}")
            
    async def start_dashboard(self, host: str = "0.0.0.0", port: int = 8000):
        """启动Web仪表板"""
        print(f"启动Web仪表板: http://{host}:{port}")
        config = uvicorn.Config(dashboard_app, host=host, port=port)
        server = uvicorn.Server(config)
        await server.serve()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="网络监控系统")
    parser.add_argument("--config", "-c", default="config.yaml", 
                       help="配置文件路径")
    parser.add_argument("--mode", "-m", choices=["monitor", "single", "analyze", 
                                                "status", "stats", "dashboard"],
                       default="monitor", help="运行模式")
    parser.add_argument("--targets", "-t", nargs="+", 
                       help="分析目标地址列表")
    parser.add_argument("--hours", type=int, default=24,
                       help="统计时间范围(小时)")
    parser.add_argument("--host", default="0.0.0.0",
                       help="Web仪表板主机地址")
    parser.add_argument("--port", type=int, default=8000,
                       help="Web仪表板端口")
    
    args = parser.parse_args()
    
    # 创建监控系统
    system = NetworkMonitoringSystem(args.config)
    
    async def run():
        """运行主程序"""
        try:
            if args.mode == "monitor":
                await system.start_monitoring()
            elif args.mode == "single":
                await system.run_single_cycle()
            elif args.mode == "analyze":
                if not args.targets:
                    print("错误: 分析模式需要指定目标地址")
                    sys.exit(1)
                await system.analyze_routes(args.targets)
            elif args.mode == "status":
                system.show_status()
            elif args.mode == "stats":
                system.show_statistics(args.hours)
            elif args.mode == "dashboard":
                await system.start_dashboard(args.host, args.port)
        except Exception as e:
            print(f"错误: {e}")
            sys.exit(1)
            
    # 运行程序
    asyncio.run(run())

if __name__ == "__main__":
    main() 