#!/bin/bash
# -*- coding: utf-8 -*-
"""
Optional Dependencies Installation Script
For macOS Systems
"""

set -e  # Exit on error

echo "=== Optional Dependencies Installation ==="
echo "This script installs optional packages for advanced features"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment does not exist, please run setup_venv.sh first"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Warning: Homebrew not found. Some packages may fail to install."
    echo "Consider installing Homebrew: https://brew.sh/"
else
    echo "Homebrew found. Installing system dependencies..."
    brew install pkg-config libffi || echo "Warning: Failed to install some system dependencies"
fi

# Set environment variables for compilation
export LDFLAGS="-L/opt/homebrew/lib"
export CPPFLAGS="-I/opt/homebrew/include"

echo ""
echo "Installing optional dependencies..."

# Data visualization packages
echo "Installing data visualization packages..."
pip install pandas matplotlib plotly || {
    echo "Warning: Failed to install data visualization packages"
    echo "You can try installing them individually:"
    echo "  pip install pandas"
    echo "  pip install matplotlib"
    echo "  pip install plotly"
}

# Network analysis packages
echo "Installing network analysis packages..."
pip install scapy netifaces python-whois dnspython || {
    echo "Warning: Failed to install network analysis packages"
    echo "You can try installing them individually:"
    echo "  pip install scapy"
    echo "  pip install netifaces"
    echo "  pip install python-whois"
    echo "  pip install dnspython"
}

# Web scraping package
echo "Installing web scraping package..."
pip install beautifulsoup4 || {
    echo "Warning: Failed to install web scraping package"
    echo "You can try: pip install beautifulsoup4"
}

echo ""
echo "=== Optional Dependencies Installation Complete ==="
echo ""
echo "If some packages failed to install, you can:"
echo "1. Install system dependencies:"
echo "   brew install pkg-config libffi"
echo ""
echo "2. Set environment variables:"
echo "   export LDFLAGS=\"-L/opt/homebrew/lib\""
echo "   export CPPFLAGS=\"-I/opt/homebrew/include\""
echo ""
echo "3. Try installing packages individually:"
echo "   pip install package_name"
echo ""
echo "4. Or use conda instead of pip for problematic packages:"
echo "   conda install package_name" 