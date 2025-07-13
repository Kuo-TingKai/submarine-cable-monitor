#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路由分析器
分析网络路由、BGP信息和网络拓扑
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import subprocess
import re

@dataclass
class RouteInfo:
    """路由信息数据类"""
    destination: str
    gateway: str
    interface: str
    metric: int
    as_path: Optional[List[str]] = None
    origin: Optional[str] = None
    next_hop: Optional[str] = None

@dataclass
class BGPInfo:
    """BGP信息数据类"""
    asn: str
    prefix: str
    as_path: List[str]
    next_hop: str
    origin: str
    local_pref: Optional[int] = None
    med: Optional[int] = None
    community: Optional[List[str]] = None

class RouteAnalyzer:
    """路由分析器主类"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
            
    def get_local_routes(self) -> List[RouteInfo]:
        """获取本地路由表"""
        routes = []
        
        try:
            # 在Unix系统上使用route命令
            result = subprocess.run(
                ['route', '-n'], 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            lines = result.stdout.strip().split('\n')
            # 跳过标题行
            for line in lines[2:]:
                parts = line.split()
                if len(parts) >= 4:
                    routes.append(RouteInfo(
                        destination=parts[0],
                        gateway=parts[1],
                        interface=parts[7] if len(parts) > 7 else '',
                        metric=int(parts[4]) if len(parts) > 4 else 0
                    ))
                    
        except subprocess.CalledProcessError:
            self.logger.warning("无法获取本地路由表")
        except FileNotFoundError:
            self.logger.warning("route命令不可用")
            
        return routes
        
    async def get_bgp_info(self, prefix: str) -> List[BGPInfo]:
        """获取BGP路由信息"""
        bgp_info = []
        
        # 使用多个BGP查询服务
        services = [
            f"https://api.bgpview.io/prefix/{prefix}",
            f"https://api.hackertarget.com/aslookup/?q={prefix}",
            f"https://api.iptoasn.com/v1/as/ip/{prefix}"
        ]
        
        for service_url in services:
            try:
                async with self.session.get(service_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        bgp_info.extend(self._parse_bgp_data(data, prefix))
                        break
            except Exception as e:
                self.logger.debug(f"BGP查询服务 {service_url} 失败: {e}")
                continue
                
        return bgp_info
        
    def _parse_bgp_data(self, data: Dict, prefix: str) -> List[BGPInfo]:
        """解析BGP数据"""
        bgp_info = []
        
        try:
            # 解析BGPView.io格式
            if 'data' in data and 'prefixes' in data['data']:
                for prefix_data in data['data']['prefixes']:
                    if 'asn' in prefix_data:
                        bgp_info.append(BGPInfo(
                            asn=str(prefix_data['asn']['asn']),
                            prefix=prefix,
                            as_path=prefix_data.get('as_path', []),
                            next_hop=prefix_data.get('next_hop', ''),
                            origin=prefix_data.get('origin', ''),
                            local_pref=prefix_data.get('local_pref'),
                            med=prefix_data.get('med'),
                            community=prefix_data.get('community', [])
                        ))
                        
        except Exception as e:
            self.logger.error(f"解析BGP数据失败: {e}")
            
        return bgp_info
        
    async def trace_route(self, destination: str, max_hops: int = 30) -> List[Dict]:
        """执行traceroute"""
        trace_result = []
        
        try:
            # 使用traceroute命令
            result = subprocess.run(
                ['traceroute', '-m', str(max_hops), destination],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # 跳过标题行
                hop_info = self._parse_traceroute_line(line)
                if hop_info:
                    trace_result.append(hop_info)
                    
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Traceroute到 {destination} 超时")
        except subprocess.CalledProcessError:
            self.logger.warning(f"Traceroute到 {destination} 失败")
        except FileNotFoundError:
            self.logger.warning("traceroute命令不可用")
            
        return trace_result
        
    def _parse_traceroute_line(self, line: str) -> Optional[Dict]:
        """解析traceroute输出行"""
        # 匹配traceroute输出格式
        pattern = r'^\s*(\d+)\s+([^\s]+)\s+([\d.]+)\s+ms'
        match = re.match(pattern, line)
        
        if match:
            return {
                'hop': int(match.group(1)),
                'hostname': match.group(2),
                'ip': match.group(2) if match.group(2).replace('.', '').isdigit() else '',
                'latency': float(match.group(3))
            }
        return None
        
    async def analyze_network_path(self, destination: str) -> Dict:
        """分析到目标地址的网络路径"""
        analysis = {
            'destination': destination,
            'timestamp': datetime.now().isoformat(),
            'local_routes': [],
            'bgp_info': [],
            'traceroute': [],
            'summary': {}
        }
        
        # 获取本地路由
        analysis['local_routes'] = self.get_local_routes()
        
        # 获取BGP信息
        analysis['bgp_info'] = await self.get_bgp_info(destination)
        
        # 执行traceroute
        analysis['traceroute'] = await self.trace_route(destination)
        
        # 生成摘要
        analysis['summary'] = self._generate_path_summary(analysis)
        
        return analysis
        
    def _generate_path_summary(self, analysis: Dict) -> Dict:
        """生成路径分析摘要"""
        summary = {
            'total_hops': len(analysis['traceroute']),
            'avg_latency': 0,
            'max_latency': 0,
            'min_latency': float('inf'),
            'as_path': [],
            'bottlenecks': []
        }
        
        # 计算延迟统计
        latencies = [hop['latency'] for hop in analysis['traceroute'] if hop['latency'] > 0]
        if latencies:
            summary['avg_latency'] = sum(latencies) / len(latencies)
            summary['max_latency'] = max(latencies)
            summary['min_latency'] = min(latencies)
            
        # 提取AS路径
        if analysis['bgp_info']:
            summary['as_path'] = analysis['bgp_info'][0].as_path
            
        # 识别瓶颈
        for i, hop in enumerate(analysis['traceroute']):
            if hop['latency'] > summary['avg_latency'] * 2:
                summary['bottlenecks'].append({
                    'hop': hop['hop'],
                    'hostname': hop['hostname'],
                    'latency': hop['latency']
                })
                
        return summary
        
    async def analyze_submarine_cable_routes(self, cable_endpoints: List[str]) -> Dict:
        """分析海缆系统路由"""
        cable_analysis = {
            'timestamp': datetime.now().isoformat(),
            'cables': {}
        }
        
        for endpoint in cable_endpoints:
            self.logger.info(f"分析海缆端点路由: {endpoint}")
            cable_analysis['cables'][endpoint] = await self.analyze_network_path(endpoint)
            
        return cable_analysis
        
    def detect_route_changes(self, old_routes: List[RouteInfo], 
                           new_routes: List[RouteInfo]) -> List[Dict]:
        """检测路由变化"""
        changes = []
        
        old_route_dict = {route.destination: route for route in old_routes}
        new_route_dict = {route.destination: route for route in new_routes}
        
        # 检测新增路由
        for dest, new_route in new_route_dict.items():
            if dest not in old_route_dict:
                changes.append({
                    'type': 'added',
                    'destination': dest,
                    'route': new_route
                })
                
        # 检测删除的路由
        for dest, old_route in old_route_dict.items():
            if dest not in new_route_dict:
                changes.append({
                    'type': 'removed',
                    'destination': dest,
                    'route': old_route
                })
                
        # 检测修改的路由
        for dest in old_route_dict:
            if dest in new_route_dict:
                old_route = old_route_dict[dest]
                new_route = new_route_dict[dest]
                
                if (old_route.gateway != new_route.gateway or 
                    old_route.metric != new_route.metric):
                    changes.append({
                        'type': 'modified',
                        'destination': dest,
                        'old_route': old_route,
                        'new_route': new_route
                    })
                    
        return changes
        
    async def get_as_info(self, asn: str) -> Optional[Dict]:
        """获取AS信息"""
        try:
            url = f"https://api.bgpview.io/asn/{asn}"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'data' in data:
                        return data['data']
        except Exception as e:
            self.logger.error(f"获取AS {asn} 信息失败: {e}")
            
        return None

async def main():
    """示例用法"""
    async with RouteAnalyzer() as analyzer:
        # 分析到香港的路由
        hk_analysis = await analyzer.analyze_network_path("203.208.60.1")
        
        print("香港路由分析结果:")
        print(json.dumps(hk_analysis['summary'], indent=2, ensure_ascii=False))
        
        # 分析海缆端点
        cable_endpoints = [
            "203.208.60.1",  # C2C香港
            "202.12.27.1",   # EAC1香港
            "202.12.28.1"    # NACS香港
        ]
        
        cable_analysis = await analyzer.analyze_submarine_cable_routes(cable_endpoints)
        
        print("\n海缆路由分析:")
        for endpoint, analysis in cable_analysis['cables'].items():
            print(f"\n{endpoint}:")
            print(f"  跳数: {analysis['summary']['total_hops']}")
            print(f"  平均延迟: {analysis['summary']['avg_latency']:.1f}ms")
            print(f"  AS路径: {' -> '.join(analysis['summary']['as_path'])}")

if __name__ == "__main__":
    asyncio.run(main()) 