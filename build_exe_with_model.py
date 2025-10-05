#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绿视率分析系统 - 包含完整模型的分离式打包脚本
确保AI模型完全下载后再进行打包
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

def clean_build_dirs():
    """清理构建目录"""
    print("清理构建目录...")
    dirs_to_clean = ['build', 'dist']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"✅ 已删除 {dir_name} 目录")
    
    print("✅ 清理完成\n")

def ensure_model_downloaded():
    """确保AI模型完全下载"""
    print("检查AI模型状态...")
    
    try:
        # 导入模型加载模块
        sys.path.insert(0, os.path.join(os.getcwd(), 'modules'))
        from image_processing import GreenViewAnalyzer
        
        print("创建分析器实例...")
        analyzer = GreenViewAnalyzer()
        
        print("开始下载/验证AI模型...")
        print("注意：首次下载可能需要5-10分钟，请耐心等待")
        
        # 强制下载模型到本地
        success = analyzer.load_model()
        
        if success:
            print("✅ AI模型验证成功")
            
            # 检查模型文件完整性
            models_dir = os.path.join(os.getcwd(), "models")
            if os.path.exists(models_dir):
                print(f"✅ 模型目录存在: {models_dir}")
                
                # 检查是否有不完整的文件
                incomplete_files = []
                for root, dirs, files in os.walk(models_dir):
                    for file in files:
                        if file.endswith('.incomplete'):
                            incomplete_files.append(os.path.join(root, file))
                
                if incomplete_files:
                    print(f"⚠️ 发现 {len(incomplete_files)} 个不完整的模型文件")
                    print("正在重新下载模型...")
                    
                    # 删除不完整的文件
                    for file_path in incomplete_files:
                        try:
                            os.remove(file_path)
                            print(f"删除不完整文件: {file_path}")
                        except:
                            pass
                    
                    # 重新加载模型
                    analyzer = GreenViewAnalyzer()
                    success = analyzer.load_model()
                    
                    if not success:
                        print("❌ 模型重新下载失败")
                        return False
                
                print("✅ 模型文件完整性检查通过")
                return True
            else:
                print("❌ 模型目录不存在")
                return False
        else:
            print("❌ AI模型下载/验证失败")
            return False
            
    except Exception as e:
        print(f"❌ 模型检查过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def build_exe_with_model():
    """执行包含完整模型的分离式打包"""
    print("开始分离式打包（包含完整AI模型）...")
    
    # 构建命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onedir',  # 分离式打包
        '--windowed',  # 无控制台窗口
        '--name=绿视率分析系统',
        '--add-data=modules;modules',
        '--add-data=models;models',  # 包含完整的模型文件
        '--add-data=data;data',
        '--hidden-import=torch',
        '--hidden-import=transformers',
        '--hidden-import=PIL',
        '--hidden-import=tkinter',
        '--hidden-import=numpy',
        '--hidden-import=requests',
        '--hidden-import=cv2',
        '--hidden-import=pandas',
        '--hidden-import=openpyxl',
        '--hidden-import=matplotlib',
        '--hidden-import=PyQt5',
        '--clean',
        '--noconfirm',
        'main.py'
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        # 执行打包
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore',
            universal_newlines=True
        )
        
        # 实时输出
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        
        rc = process.poll()
        if rc == 0:
            print("✅ 打包成功！")
            return True
        else:
            print(f"❌ 打包失败，退出码: {rc}")
            return False
            
    except Exception as e:
        print(f"❌ 打包过程中出现异常: {e}")
        return False

def verify_model_in_build():
    """验证打包结果中的模型文件"""
    print("验证打包结果中的模型文件...")
    
    models_path = Path('dist/绿视率分析系统/_internal/models')
    
    if not models_path.exists():
        print("❌ 打包结果中未找到models目录")
        return False
    
    # 检查模型文件
    model_dir = models_path / 'models--nvidia--segformer-b5-finetuned-cityscapes-1024-1024'
    
    if not model_dir.exists():
        print("❌ 打包结果中未找到模型目录")
        return False
    
    # 检查是否有不完整的文件
    incomplete_files = list(model_dir.rglob('*.incomplete'))
    
    if incomplete_files:
        print(f"❌ 打包结果中发现 {len(incomplete_files)} 个不完整的模型文件:")
        for file in incomplete_files:
            print(f"   - {file}")
        return False
    
    # 检查关键文件
    snapshots_dir = model_dir / 'snapshots'
    if not snapshots_dir.exists():
        print("❌ 模型snapshots目录不存在")
        return False
    
    # 统计文件数量
    total_files = len(list(model_dir.rglob('*')))
    print(f"✅ 模型文件验证通过，共 {total_files} 个文件")
    
    return True

def check_build_result():
    """检查构建结果"""
    dist_dir = Path('dist/绿视率分析系统')
    
    if not dist_dir.exists():
        print("❌ 构建失败：未找到输出目录")
        return False
    
    exe_file = dist_dir / '绿视率分析系统.exe'
    internal_dir = dist_dir / '_internal'
    
    if not exe_file.exists():
        print("❌ 构建失败：未找到exe文件")
        return False
    
    if not internal_dir.exists():
        print("❌ 构建失败：未找到_internal目录")
        return False
    
    # 验证模型文件
    if not verify_model_in_build():
        return False
    
    # 获取文件大小
    exe_size = exe_file.stat().st_size / (1024 * 1024)  # MB
    
    # 计算_internal目录大小
    internal_size = 0
    file_count = 0
    for file_path in internal_dir.rglob('*'):
        if file_path.is_file():
            internal_size += file_path.stat().st_size
            file_count += 1
    internal_size = internal_size / (1024 * 1024)  # MB
    
    print("\n📦 构建结果:")
    print(f"   主程序: {exe_file}")
    print(f"   大小: {exe_size:.1f} MB")
    print(f"   依赖目录: {internal_dir}")
    print(f"   大小: {internal_size:.1f} MB")
    print(f"   文件数量: {file_count}")
    print(f"   总大小: {exe_size + internal_size:.1f} MB")
    
    return True

def create_launcher_script():
    """创建启动脚本"""
    launcher_content = '''@echo off
chcp 65001 >nul
echo ========================================
echo 绿视率分析系统 - 完整模型版
echo ========================================
echo.

REM 检查exe文件是否存在
if not exist "绿视率分析系统.exe" (
    echo ❌ 未找到主程序文件
    echo 请确保在正确的目录中运行此脚本
    pause
    exit /b 1
)

REM 检查_internal目录是否存在
if not exist "_internal" (
    echo ❌ 未找到依赖文件目录
    echo 请确保_internal目录与exe文件在同一位置
    pause
    exit /b 1
)

REM 检查模型文件是否存在
if not exist "_internal\\models" (
    echo ❌ 未找到AI模型文件
    echo 请确保模型文件已正确打包
    pause
    exit /b 1
)

echo ✅ 文件检查通过
echo.
echo 📋 部署包信息:
echo    - 主程序: 绿视率分析系统.exe
echo    - 依赖库: _internal目录
echo    - AI模型: 已预装，无需下载
echo    - 特点: 离线运行，即开即用
echo.
echo 🚀 正在启动程序...
echo 注意: 首次启动可能需要10-20秒初始化
echo.

REM 启动程序
start "绿视率分析系统" "绿视率分析系统.exe"

echo ✅ 程序已启动
echo.
echo 💡 使用提示:
echo 1. 本地图片分析: 选择图片文件或文件夹
echo 2. 街景下载: 输入坐标或使用坐标获取功能
echo 3. 结果导出: 支持Excel表格和图片输出
echo 4. 离线运行: AI模型已预装，无需网络连接
echo.
echo 如果程序未正常显示，请检查:
echo - 防火墙设置
echo - 杀毒软件拦截
echo - 系统兼容性
echo - 磁盘空间是否充足
echo.
echo 按任意键退出...
pause >nul
'''
    
    launcher_path = Path('dist/绿视率分析系统/启动程序.bat')
    with open(launcher_path, 'w', encoding='utf-8') as f:
        f.write(launcher_content)
    
    print(f"✅ 已创建启动脚本: {launcher_path}")

def create_readme():
    """创建说明文件"""
    readme_content = '''绿视率分析系统 - 完整模型版

🎯 版本特点:
✅ AI模型已预装 - 无需下载
✅ 离线运行 - 无需网络连接*
✅ 即开即用 - 启动即可分析
✅ 稳定可靠 - 消除网络依赖问题

*注：仅街景下载功能需要网络连接

📦 文件结构:
绿视率分析系统/
├── 绿视率分析系统.exe     # 主程序
├── _internal/             # 依赖库文件
│   ├── models/           # AI模型文件（已预装）
│   ├── torch/            # PyTorch框架
│   ├── transformers/     # Hugging Face库
│   └── ...              # 其他依赖
├── 启动程序.bat           # 启动脚本
└── README.txt            # 使用说明

🚀 启动方法:
方法1: 双击 "启动程序.bat" (推荐)
方法2: 双击 "绿视率分析系统.exe"
方法3: 命令行运行 "绿视率分析系统.exe"

⚠️ 重要提示:
1. exe文件和_internal目录必须在同一位置
2. 移动时请整个文件夹一起移动
3. 首次启动需要10-20秒初始化
4. AI模型已预装，无需网络下载
5. 确保有足够磁盘空间（约5GB）

🔧 功能说明:
- 本地图片分析: 支持JPG/PNG/BMP格式
- 街景图片下载: 集成百度街景API（需网络）
- 坐标自动获取: 基于百度地图API（需网络）
- 结果导出: Excel表格和图片输出
- GPU加速: 自动检测CUDA支持
- 离线分析: AI模型已预装，可离线运行

🛠️ 故障排除:
问题: 程序无法启动
解决: 检查_internal目录是否完整

问题: 提示模型加载失败
解决: 检查_internal/models目录是否存在

问题: 性能缓慢
解决: 关闭其他占用内存的程序，使用GPU模式

问题: 杀毒软件误报
解决: 将程序目录添加到杀毒软件白名单

📊 系统要求:
- 操作系统: Windows 10/11
- 内存: 至少4GB (推荐8GB)
- 磁盘: 至少10GB可用空间
- 网络: 仅街景下载功能需要
- GPU: 可选，支持CUDA 12.1

🎉 版本优势:
相比之前版本，本版本解决了:
- ❌ 模型下载失败问题
- ❌ 网络连接依赖问题
- ❌ 首次启动缓慢问题
- ❌ 离线环境无法使用问题

📞 技术支持:
查看程序logs目录下的日志文件获取详细错误信息

版本: v1.3 完整模型版
构建时间: 2025-01-08
模型版本: SegFormer-B5 (预装)
'''
    
    readme_path = Path('dist/绿视率分析系统/README.txt')
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"✅ 已创建说明文件: {readme_path}")

def main():
    """主函数"""
    print("========================================")
    print("绿视率分析系统 - 完整模型版打包")
    print("========================================")
    print()
    
    # 检查当前目录
    if not os.path.exists('main.py'):
        print("❌ 错误：未找到main.py文件")
        print("请在项目根目录中运行此脚本")
        return False
    
    try:
        # 1. 清理构建目录
        clean_build_dirs()
        
        # 2. 确保AI模型完全下载
        if not ensure_model_downloaded():
            print("❌ AI模型准备失败，无法继续打包")
            return False
        
        # 3. 执行打包
        if not build_exe_with_model():
            return False
        
        # 4. 检查构建结果
        if not check_build_result():
            return False
        
        # 5. 创建启动脚本
        create_launcher_script()
        
        # 6. 创建说明文件
        create_readme()
        
        print("\n🎉 完整模型版打包完成！")
        print("\n📁 输出目录: dist/绿视率分析系统/")
        print("\n✨ 完整模型版的优势:")
        print("- 🚀 AI模型已预装，无需下载")
        print("- 📦 离线运行，即开即用")
        print("- ⚡ 启动速度快，稳定可靠")
        print("- 🔄 消除网络依赖问题")
        print("- 💾 适合离线环境部署")
        print("\n📋 使用方法:")
        print("1. 将整个 'dist/绿视率分析系统' 文件夹复制到目标机器")
        print("2. 双击 '启动程序.bat' 或直接运行 '绿视率分析系统.exe'")
        print("3. 程序启动后即可直接进行图片分析，无需等待模型下载")
        print("\n⚠️ 重要: exe文件和_internal目录必须保持在同一位置")
        
        return True
        
    except Exception as e:
        print(f"❌ 打包过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    if not success:
        print("\n❌ 完整模型版打包失败！")
        print("\n💡 建议:")
        print("1. 检查网络连接，确保能访问huggingface.co")
        print("2. 确保有足够磁盘空间（至少10GB）")
        print("3. 检查防火墙和代理设置")
        print("4. 尝试重新运行脚本")
        sys.exit(1)
    else:
        print("\n✅ 完整模型版打包成功！")
        print("\n🎯 下一步:")
        print("1. 测试打包的exe文件是否能正常启动")
        print("2. 验证AI模型加载功能是否正常")
        print("3. 进行完整的功能测试")
        print("4. 准备分发给最终用户")