#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Route Analyzer
Analyze network routes, BGP information and network topology
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
import platform

@dataclass
class RouteInfo:
    """Route information data class"""
    destination: str
    gateway: str
    interface: str
    metric: int
    as_path: Optional[List[str]] = None
    origin: Optional[str] = None
    next_hop: Optional[str] = None

@dataclass
class BGPInfo:
    """BGP information data class"""
    asn: str
    prefix: str
    as_path: List[str]
    next_hop: str
    origin: str
    local_pref: Optional[int] = None
    med: Optional[int] = None
    community: Optional[List[str]] = None

class RouteAnalyzer:
    """Main route analyzer class"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            
    def get_local_routes(self) -> List[RouteInfo]:
        """Get local routing table (auto-adapt for Linux/macOS)"""
        routes = []
        try:
            system = platform.system()
            if system == 'Linux':
                # Use route -n on Linux
                result = subprocess.run(['route', '-n'], capture_output=True, text=True, check=True)
                lines = result.stdout.strip().split('\n')
                for line in lines[2:]:  # Skip header
                    parts = line.split()
                    if len(parts) >= 8:
                        routes.append(RouteInfo(destination=parts[0], gateway=parts[1], iface=parts[-1]))
            elif system == 'Darwin':
                # Use netstat -rn on macOS
                result = subprocess.run(['netstat', '-rn'], capture_output=True, text=True, check=True)
                lines = result.stdout.strip().split('\n')
                header_found = False
                for line in lines:
                    if not header_found:
                        if line.lower().startswith('destination'):
                            header_found = True
                        continue
                    parts = line.split()
                    if len(parts) >= 6:
                        routes.append(RouteInfo(destination=parts[0], gateway=parts[1], iface=parts[-1]))
            else:
                self.logger.warning(f"Unsupported OS for route table: {system}")
        except subprocess.CalledProcessError:
            self.logger.warning("Unable to get local routing table")
        except FileNotFoundError:
            self.logger.warning("route/netstat command not available")
        return routes
        
    async def get_bgp_info(self, prefix: str) -> List[BGPInfo]:
        """Get BGP route information"""
        bgp_info = []
        
        # Use multiple BGP query services
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
                self.logger.debug(f"BGP query service {service_url} failed: {e}")
                continue
                
        return bgp_info
        
    def _parse_bgp_data(self, data: Dict, prefix: str) -> List[BGPInfo]:
        """Parse BGP data"""
        bgp_info = []
        
        try:
            # Parse BGPView.io format
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
            self.logger.error(f"Failed to parse BGP data: {e}")
            
        return bgp_info
        
    async def trace_route(self, destination: str, max_hops: int = 30) -> List[Dict]:
        """Execute traceroute"""
        trace_result = []
        
        try:
            # Use traceroute command
            result = subprocess.run(
                ['traceroute', '-m', str(max_hops), destination],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # Skip header line
                hop_info = self._parse_traceroute_line(line)
                if hop_info:
                    trace_result.append(hop_info)
                    
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Traceroute to {destination} timed out")
        except subprocess.CalledProcessError:
            self.logger.warning(f"Traceroute to {destination} failed")
        except FileNotFoundError:
            self.logger.warning("traceroute command not available")
            
        return trace_result
        
    def _parse_traceroute_line(self, line: str) -> Optional[Dict]:
        """Parse traceroute output line"""
        # Match traceroute output format
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
        """Analyze network path to destination address"""
        analysis = {
            'destination': destination,
            'timestamp': datetime.now().isoformat(),
            'local_routes': [],
            'bgp_info': [],
            'traceroute': [],
            'summary': {}
        }
        
        # Get local routes
        analysis['local_routes'] = self.get_local_routes()
        
        # Get BGP information
        analysis['bgp_info'] = await self.get_bgp_info(destination)
        
        # Execute traceroute
        analysis['traceroute'] = await self.trace_route(destination)
        
        # Generate summary
        analysis['summary'] = self._generate_path_summary(analysis)
        
        return analysis
        
    def _generate_path_summary(self, analysis: Dict) -> Dict:
        """Generate path analysis summary"""
        summary = {
            'total_hops': len(analysis['traceroute']),
            'avg_latency': 0,
            'max_latency': 0,
            'min_latency': float('inf'),
            'as_path': [],
            'bottlenecks': []
        }
        
        # Calculate latency statistics
        latencies = [hop['latency'] for hop in analysis['traceroute'] if hop['latency'] > 0]
        if latencies:
            summary['avg_latency'] = sum(latencies) / len(latencies)
            summary['max_latency'] = max(latencies)
            summary['min_latency'] = min(latencies)
            
        # Extract AS path
        if analysis['bgp_info']:
            summary['as_path'] = analysis['bgp_info'][0].as_path
            
        # Identify bottlenecks
        for i, hop in enumerate(analysis['traceroute']):
            if hop['latency'] > summary['avg_latency'] * 2:
                summary['bottlenecks'].append({
                    'hop': hop['hop'],
                    'hostname': hop['hostname'],
                    'latency': hop['latency']
                })
                
        return summary
        
    async def analyze_submarine_cable_routes(self, cable_endpoints: List[str]) -> Dict:
        """Analyze submarine cable routes"""
        cable_analysis = {
            'timestamp': datetime.now().isoformat(),
            'cables': {}
        }
        
        for endpoint in cable_endpoints:
            self.logger.info(f"Analyzing submarine cable endpoint routes: {endpoint}")
            cable_analysis['cables'][endpoint] = await self.analyze_network_path(endpoint)
            
        return cable_analysis
        
    def detect_route_changes(self, old_routes: List[RouteInfo], 
                           new_routes: List[RouteInfo]) -> List[Dict]:
        """Detect route changes"""
        changes = []
        
        old_route_dict = {route.destination: route for route in old_routes}
        new_route_dict = {route.destination: route for route in new_routes}
        
        # Detect added routes
        for dest, new_route in new_route_dict.items():
            if dest not in old_route_dict:
                changes.append({
                    'type': 'added',
                    'destination': dest,
                    'route': new_route
                })
                
        # Detect removed routes
        for dest, old_route in old_route_dict.items():
            if dest not in new_route_dict:
                changes.append({
                    'type': 'removed',
                    'destination': dest,
                    'route': old_route
                })
                
        # Detect modified routes
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
        """Get AS information"""
        try:
            url = f"https://api.bgpview.io/asn/{asn}"
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'data' in data:
                        return data['data']
        except Exception as e:
            self.logger.error(f"Failed to get AS {asn} information: {e}")
            
        return None

async def main():
    """Example usage"""
    async with RouteAnalyzer() as analyzer:
        # Analyze routes to Hong Kong
        hk_analysis = await analyzer.analyze_network_path("203.208.60.1")
        
        print("Hong Kong Route Analysis Result:")
        print(json.dumps(hk_analysis['summary'], indent=2, ensure_ascii=False))
        
        # Analyze submarine cable endpoints
        cable_endpoints = [
            "203.208.60.1",  # C2C Hong Kong
            "202.12.27.1",   # EAC1 Hong Kong
            "202.12.28.1"    # NACS Hong Kong
        ]
        
        cable_analysis = await analyzer.analyze_submarine_cable_routes(cable_endpoints)
        
        print("\nSubmarine Cable Route Analysis:")
        for endpoint, analysis in cable_analysis['cables'].items():
            print(f"\n{endpoint}:")
            print(f"  Hops: {analysis['summary']['total_hops']}")
            print(f"  Average Latency: {analysis['summary']['avg_latency']:.1f}ms")
            print(f"  AS Path: {' -> '.join(analysis['summary']['as_path'])}")

if __name__ == "__main__":
    asyncio.run(main()) 