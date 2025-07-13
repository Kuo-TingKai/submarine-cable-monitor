#!/bin/bash
# -*- coding: utf-8 -*-
"""
Virtual Environment Setup Script
For macOS Systems
"""

set -e  # Exit on error

echo "=== Network Monitoring System Virtual Environment Setup ==="
echo "For macOS Systems"

# Check Python version
echo "Checking Python version..."
python3 --version

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install core dependencies
echo "Installing core dependencies..."
pip install -r requirements.txt

# Ask if user wants to install optional dependencies
echo ""
echo "Core dependencies installed successfully!"
echo ""
echo "Optional dependencies are available for advanced features:"
echo "  - Data visualization (pandas, matplotlib, plotly)"
echo "  - Advanced network analysis (scapy, netifaces, python-whois)"
echo "  - Web scraping (beautifulsoup4)"
echo ""
read -p "Do you want to install optional dependencies? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing optional dependencies..."
    echo "Note: This may take some time and require additional system tools."
    
    # Install optional dependencies one by one to handle errors gracefully
    pip install pandas matplotlib plotly || echo "Warning: Failed to install data visualization packages"
    pip install scapy netifaces python-whois dnspython || echo "Warning: Failed to install network analysis packages"
    pip install beautifulsoup4 || echo "Warning: Failed to install web scraping package"
    
    echo "Optional dependencies installation complete!"
else
    echo "Skipping optional dependencies. You can install them later with:"
    echo "  pip install -r requirements_full.txt"
fi

echo ""
echo "=== Virtual Environment Setup Complete ==="
echo ""
echo "Usage:"
echo "1. Activate virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Run monitoring system:"
echo "   python main.py --mode monitor"
echo ""
echo "3. Start Web dashboard:"
echo "   python main.py --mode dashboard"
echo ""
echo "4. Run demo:"
echo "   python run_example.py"
echo ""
echo "5. Deactivate virtual environment:"
echo "   deactivate"
echo ""
echo "Note: You need to activate the virtual environment before each use!"
echo ""
echo "If you encounter issues with optional packages, try:"
echo "  brew install pkg-config"
echo "  brew install libffi"
echo "  export LDFLAGS=\"-L/opt/homebrew/lib\""
echo "  export CPPFLAGS=\"-I/opt/homebrew/include\"" 