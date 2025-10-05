#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度街景图片绿视率分析工具 - 主程序入口

功能：
1. 程序启动和初始化
2. GUI界面启动
3. 异常处理和日志记录
4. 系统环境检查
"""

import sys
import os
import logging
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from modules.gui_interface import MainWindow
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有依赖已正确安装")
    sys.exit(1)

def setup_logging():
    """设置日志系统"""
    # 创建logs目录
    logs_dir = os.path.join(project_root, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # 配置日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 创建日志文件名（包含日期）
    log_filename = f"green_rate_{datetime.now().strftime('%Y%m%d')}.log"
    log_filepath = os.path.join(logs_dir, log_filename)
    
    # 配置日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

def check_dependencies():
    """检查系统依赖"""
    logger = logging.getLogger(__name__)
    
    # 检查是否在打包环境中运行
    if getattr(sys, 'frozen', False):
        # 在PyInstaller打包的exe中运行，跳过依赖检查
        logger.info("在打包环境中运行，跳过依赖检查")
        return True, "打包环境，依赖已内置"
    
    missing_deps = []
    
    # 检查必要的Python包
    required_packages = {
        'PyQt5': 'PyQt5',
        'requests': 'requests', 
        'Pillow': 'PIL',  # Pillow库通过PIL导入
        'pandas': 'pandas',
        'openpyxl': 'openpyxl',
        'numpy': 'numpy',
        'torch': 'torch',
        'transformers': 'transformers'
    }
    
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
            logger.info(f"✓ {package_name} 已安装")
        except ImportError:
            missing_deps.append(package_name)
            logger.error(f"✗ {package_name} 未安装")
    
    if missing_deps:
        error_msg = f"缺少以下依赖包:\n{', '.join(missing_deps)}\n\n请运行以下命令安装:\npip install {' '.join(missing_deps)}"
        logger.error(error_msg)
        return False, error_msg
    
    return True, "所有依赖检查通过"

def check_directories():
    """检查并创建必要的目录"""
    logger = logging.getLogger(__name__)
    
    required_dirs = [
        'data',
        'output', 
        'models',
        'tests',
        'logs'
    ]
    
    for dir_name in required_dirs:
        dir_path = os.path.join(project_root, dir_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            logger.info(f"创建目录: {dir_path}")
        else:
            logger.info(f"目录已存在: {dir_path}")

def main():
    """主函数"""
    # 设置日志系统
    logger = setup_logging()
    logger.info("="*50)
    logger.info("百度街景图片绿视率分析工具启动")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"工作目录: {project_root}")
    logger.info("="*50)
    
    try:
        # 检查目录结构
        check_directories()
        
        # 检查依赖
        deps_ok, deps_msg = check_dependencies()
        if not deps_ok:
            # 如果在GUI环境中，显示错误对话框
            try:
                app = QApplication(sys.argv)
                QMessageBox.critical(None, "依赖检查失败", deps_msg)
                sys.exit(1)
            except:
                print(deps_msg)
                sys.exit(1)
        
        logger.info("系统检查完成，启动GUI界面...")
        
        # 创建QApplication实例
        app = QApplication(sys.argv)
        
        # 设置应用程序属性
        app.setApplicationName("百度街景图片绿视率分析工具")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("GreenView Analytics")
        
        # 设置高DPI支持
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # 创建主窗口
        logger.info("创建主窗口...")
        window = MainWindow()
        
        # 显示窗口
        window.show()
        logger.info("GUI界面启动成功")
        
        # 运行应用程序
        exit_code = app.exec_()
        logger.info(f"应用程序退出，退出码: {exit_code}")
        sys.exit(exit_code)
        
    except Exception as e:
        error_msg = f"程序启动失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # 尝试显示错误对话框
        try:
            if 'app' not in locals():
                app = QApplication(sys.argv)
            QMessageBox.critical(None, "启动错误", error_msg)
        except:
            print(error_msg)
        
        sys.exit(1)

if __name__ == "__main__":
    main()