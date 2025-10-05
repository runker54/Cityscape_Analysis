# 🌿 绿视率分析系统 (Cityscape Analysis)

一款基于AI深度学习的城市绿视率自动化分析工具，通过百度街景API获取街景图片，使用NVIDIA SegFormer模型进行语义分割，自动计算城市绿化覆盖率。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green.svg)
![PyTorch](https://img.shields.io/badge/AI-PyTorch-red.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📋 目录

- [功能特性](#-功能特性)
- [技术架构](#-技术架构)
- [安装说明](#-安装说明)
- [使用指南](#-使用指南)
- [项目结构](#-项目结构)
- [API配置](#-api配置)
- [模型说明](#-模型说明)
- [输出结果](#-输出结果)
- [常见问题](#-常见问题)
- [贡献指南](#-贡献指南)
- [许可证](#-许可证)

## 🚀 功能特性

### 核心功能
- **🗺️ 街景数据采集**: 通过百度街景API自动下载指定区域街景图片
- **🤖 AI语义分割**: 使用NVIDIA SegFormer模型进行城市景观语义分割
- **📊 绿视率计算**: 自动计算每张图片的植被覆盖率（绿视率）
- **📈 数据可视化**: 生成分析结果图片，直观显示植被分布
- **📋 报表导出**: 自动生成Excel报表，包含详细的分析数据

### 界面特性
- **🖥️ 图形化界面**: 基于PyQt5的现代化GUI界面
- **📍 坐标输入**: 支持单点、批量坐标输入和Excel文件导入
- **⚙️ 设备选择**: 自动检测并支持GPU/CPU计算
- **📊 实时进度**: 实时显示下载和分析进度
- **🎯 结果预览**: 支持分析结果的实时预览

## 🏗️ 技术架构

### 核心技术栈
- **编程语言**: Python 3.8+
- **GUI框架**: PyQt5
- **深度学习**: PyTorch + Transformers
- **图像处理**: OpenCV + Pillow
- **数据处理**: Pandas + NumPy
- **网络请求**: Requests

### AI模型
- **模型**: NVIDIA SegFormer-B5
- **训练数据**: Cityscapes数据集
- **分辨率**: 1024x1024
- **类别数**: 19个城市景观类别
- **植被类别ID**: 18

## 📦 安装说明

### 环境要求
- Python 3.8 或更高版本
- Windows 10/11 (推荐)
- 4GB+ RAM
- GPU (可选，用于加速推理)

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/runker54/Cityscape_Analysis.git
cd Cityscape_Analysis
```

2. **创建虚拟环境**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **运行程序**
```bash
python main.py
```

### 打包版本
如果您不想配置Python环境，可以下载预编译的exe版本：
- 前往 [Releases](https://github.com/runker54/Cityscape_Analysis/releases) 页面
- 下载最新版本的压缩包
- 解压后直接运行 `绿视率分析系统.exe`

## 📖 使用指南

### 1. 配置百度API
1. 访问 [百度地图开放平台](https://lbsyun.baidu.com/)
2. 注册账号并创建应用
3. 获取AK (Access Key)
4. 在程序中输入您的API密钥

### 2. 准备坐标数据
支持三种输入方式：
- **单点输入**: 直接输入经纬度坐标
- **批量输入**: 每行一个坐标，格式：`经度,纬度`
- **Excel导入**: 包含lon和lat列的Excel文件

### 3. 开始分析
1. 设置保存路径
2. 点击"开始下载"获取街景图片
3. 点击"开始分析"进行AI分析
4. 点击"导出报表"生成Excel结果

### 4. 查看结果
- **原始图片**: `images/original/` 目录
- **分析图片**: `images/analysis/` 目录
- **Excel报表**: 包含坐标、路径、绿视率等信息

## 📁 项目结构

```
Cityscape_Analysis/
├── main.py                    # 主程序入口
├── requirements.txt           # 依赖包列表
├── README.md                 # 项目说明文档
├── .gitignore               # Git忽略文件
├── build_exe_with_model.py  # 打包脚本
├── modules/                 # 核心功能模块
│   ├── __init__.py
│   ├── gui_interface.py     # GUI界面模块
│   ├── data_collection.py   # 数据采集模块
│   ├── image_processing.py  # 图像处理模块
│   ├── result_export.py     # 结果导出模块
│   └── coordinate_collector.py # 坐标收集模块
├── dist/                    # 打包输出目录
├── logs/                    # 日志文件目录
├── models/                  # AI模型存储目录
└── data/                    # 数据存储目录
```

## 🔑 API配置

### 百度街景API参数
- **端点**: `http://api.map.baidu.com/panorama/v2`
- **坐标系**: WGS84
- **图片尺寸**: 1024x512 (默认)
- **视野角度**: 90° (可调节)
- **俯仰角**: 0° (可调节)

### API限制
- 每日调用次数限制
- 并发请求限制
- 图片分辨率限制

详细信息请参考 [百度地图API文档](https://lbsyun.baidu.com/index.php?title=viewstatic)

## 🤖 模型说明

### SegFormer模型特性
- **架构**: Transformer-based语义分割模型
- **优势**: 高精度、高效率、多尺度特征融合
- **类别**: 支持19个Cityscapes类别
- **植被识别**: 专门优化的植被分割能力

### 支持的语义类别
0. road, 1. sidewalk, 2. building, 3. wall, 4. fence, 5. pole, 6. traffic light, 7. traffic sign, 8. vegetation, 9. terrain, 10. sky, 11. person, 12. rider, 13. car, 14. truck, 15. bus, 16. train, 17. motorcycle, 18. bicycle

## 📊 输出结果

### Excel报表字段
| 字段名 | 描述 | 示例 |
|--------|------|------|
| 序号 | 图片编号 | 1, 2, 3... |
| 经度 | WGS84经度坐标 | 116.3974 |
| 纬度 | WGS84纬度坐标 | 39.9093 |
| 原始图片路径 | 街景图片保存路径 | images/original/1.jpg |
| 分析图片路径 | 分割结果图片路径 | images/analysis/1_analysis.jpg |
| 绿视率(%) | 植被覆盖率百分比 | 25.67 |
| 下载时间 | 图片下载时间戳 | 2024-01-01 12:00:00 |
| 分析时间 | AI分析时间戳 | 2024-01-01 12:01:00 |

### 图片输出
- **原始图片**: 从百度街景API下载的原始街景图片
- **分析图片**: 植被区域高亮显示的分割结果图片
- **对比图片**: 原始图片与分析结果的并排对比

## ❓ 常见问题

### Q: 程序运行缓慢怎么办？
A: 
- 确保使用GPU加速（如果有NVIDIA显卡）
- 减少批量处理的图片数量
- 关闭其他占用内存的程序

### Q: API调用失败怎么办？
A:
- 检查网络连接
- 验证API密钥是否正确
- 确认API配额是否充足
- 检查坐标格式是否正确

### Q: 模型下载失败怎么办？
A:
- 检查网络连接
- 使用VPN或代理
- 手动下载模型文件到models目录

### Q: 绿视率计算不准确怎么办？
A:
- 检查图片质量
- 确认坐标位置是否正确
- 调整API参数（视野角度、俯仰角）

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 开发规范
- 遵循PEP 8代码规范
- 添加适当的注释和文档
- 编写单元测试
- 更新README文档

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 联系方式

- **项目地址**: https://github.com/runker54/Cityscape_Analysis
- **问题反馈**: [Issues](https://github.com/runker54/Cityscape_Analysis/issues)
- **功能建议**: [Discussions](https://github.com/runker54/Cityscape_Analysis/discussions)

## 🙏 致谢

- [NVIDIA](https://github.com/NVlabs/SegFormer) - SegFormer模型
- [Hugging Face](https://huggingface.co/) - Transformers库
- [百度地图](https://lbsyun.baidu.com/) - 街景API服务
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI框架

---

⭐ 如果这个项目对您有帮助，请给我们一个星标！

🐛 发现问题？请提交 [Issue](https://github.com/runker54/Cityscape_Analysis/issues)

💡 有好的想法？欢迎提交 [Pull Request](https://github.com/runker54/Cityscape_Analysis/pulls)