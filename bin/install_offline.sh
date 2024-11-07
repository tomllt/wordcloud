#!/bin/bash

echo "Installing dependencies from local packages..."

# 检查Python和pip是否安装
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    exit 1
fi

if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed"
    exit 1
fi

# 创建并激活虚拟环境  
python3 -m venv venv
source venv/bin/activate

# 更新pip
python -m pip install --upgrade pip

# 从本地安装依赖
pip install --no-index --find-links packages -r requirements.txt

echo "Installation completed successfully!"