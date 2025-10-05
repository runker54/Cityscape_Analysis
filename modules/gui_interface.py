#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI界面模块 - PyQt5主界面设计和用户交互

功能：
1. 主窗口界面设计
2. 用户输入处理
3. 进度显示和状态更新
4. 模块集成和工作流控制
"""

import sys
import os
import gc
import threading
from typing import Optional, List
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QTextEdit, QPushButton, QProgressBar,
    QFileDialog, QMessageBox, QTabWidget, QGroupBox, QSpinBox,
    QCheckBox, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QFrame, QScrollArea, QRadioButton, QStatusBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QPixmap, QIcon, QPalette, QColor

# 导入自定义模块
from .data_collection import BaiduStreetViewCollector
from .image_processing import GreenViewAnalyzer
from .result_export import ResultExporter
from .coordinate_collector import CoordinateCollector

class WorkerThread(QThread):
    """工作线程类，用于执行耗时任务"""
    
    progress_updated = pyqtSignal(int, int, str)  # 当前进度, 总数, 消息
    task_completed = pyqtSignal(str, bool)  # 任务名称, 是否成功
    analysis_results_ready = pyqtSignal(list)  # 分析结果
    error_occurred = pyqtSignal(str)  # 错误消息
    
    def __init__(self, task_type: str, **kwargs):
        super().__init__()
        self.task_type = task_type
        self.kwargs = kwargs
        self.is_cancelled = False
    
    def run(self):
        """运行任务"""
        try:
            if self.task_type == "download":
                self._run_download_task()
            elif self.task_type == "analyze":
                self._run_analyze_task()
            elif self.task_type == "export":
                self._run_export_task()
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            # 任务完成后清理内存
            self._cleanup_memory()
    
    def _cleanup_memory(self):
        """清理内存"""
        try:
            # 清理任务参数
            if hasattr(self, 'kwargs'):
                self.kwargs.clear()
            
            # 强制垃圾回收
            gc.collect()
            
            # 如果有CUDA，清理GPU缓存
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
        except Exception as e:
            print(f"内存清理失败: {e}")

    def _run_download_task(self):
        """执行下载任务"""
        collector = self.kwargs['collector']
        coordinates = self.kwargs['coordinates']
        save_dir = self.kwargs['save_dir']
        
        def progress_callback(current, total, result):
            if not self.is_cancelled:
                message = f"下载第 {current}/{total} 张图片"
                if result['success']:
                    message += f" - 成功: {result['filename']}"
                else:
                    message += f" - 失败: {result.get('error', '未知错误')}"
                self.progress_updated.emit(current, total, message)
        
        try:
            results = collector.download_batch(coordinates, save_dir, progress_callback)
            
            if not self.is_cancelled:
                self.task_completed.emit("download", True)
        finally:
            # 清理局部变量
            del collector, coordinates, save_dir
            gc.collect()
    
    def _run_analyze_task(self):
        """执行分析任务"""
        analyzer = self.kwargs['analyzer']
        image_paths = self.kwargs['image_paths']
        output_dir = self.kwargs['output_dir']
        exporter = self.kwargs.get('exporter')  # 获取导出器实例
        
        # 创建综合分析图片输出目录
        comprehensive_dir = os.path.join(output_dir, 'comprehensive_analysis')
        os.makedirs(comprehensive_dir, exist_ok=True)
        
        def progress_callback(current, total, result):
            if not self.is_cancelled:
                message = f"分析第 {current}/{total} 张图片"
                if 'error' not in result:
                    message += f" - 绿视率: {result['green_view_rate']:.2f}%"
                    
                    # 根据复选框状态决定是否生成综合分析图片
                    generate_images = self.kwargs.get('generate_images', True)  # 默认生成
                    if exporter and 'segmentation_map' in result and generate_images:
                        try:
                            original_path = result.get('image_path', result.get('original_image_path', ''))
                            if original_path:
                                filename = os.path.splitext(os.path.basename(original_path))[0]
                                comprehensive_path = os.path.join(comprehensive_dir, f"{filename}_comprehensive_analysis.png")
                                
                                # 生成综合分析图片
                                if exporter.generate_comprehensive_analysis_image(result, comprehensive_path):
                                    result['comprehensive_analysis_path'] = comprehensive_path
                                    message += " - 综合图片已生成"
                        except Exception as e:
                            print(f"生成综合分析图片失败: {e}")
                else:
                    message += f" - 失败: {result['error']}"
                
                # 每处理10张图片进行一次内存清理
                if current % 10 == 0:
                    try:
                        gc.collect()
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    except:
                        pass
                
                self.progress_updated.emit(current, total, message)
        
        try:
            # 根据复选框状态决定是否保存分析图片
            generate_images = self.kwargs.get('generate_images', True)
            results = analyzer.analyze_batch(image_paths, output_dir, progress_callback, save_analysis=generate_images)
            
            if not self.is_cancelled:
                # 发出分析结果信号
                self.analysis_results_ready.emit(results)
                # 发出任务完成信号
                self.task_completed.emit("analyze", True)
        finally:
            # 清理局部变量
            del analyzer, image_paths, output_dir
            if exporter:
                del exporter
            gc.collect()
    
    def _run_export_task(self):
        """执行导出任务"""
        exporter = self.kwargs['exporter']
        output_path = self.kwargs['output_path']
        
        try:
            success = exporter.export_to_excel(output_path)
            
            if not self.is_cancelled:
                self.task_completed.emit("export", success)
        finally:
            # 清理局部变量
            del exporter, output_path
            gc.collect()
    
    def cancel(self):
        """取消任务"""
        self.is_cancelled = True
        # 取消时也清理内存
        self._cleanup_memory()

class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("百度街景图片绿视率分析工具 v1.0")
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化组件
        self.collector = None
        self.analyzer = None
        self.exporter = ResultExporter()
        self.coordinate_collector = CoordinateCollector()
        self.worker_thread = None
        
        # 数据存储
        self.coordinates = []
        self.download_results = []
        self.analysis_results = []
        self.current_save_dir = ""
        
        # 初始化界面
        self.init_ui()
        self.init_style()
        
        # 状态管理
        self.model_loaded = False
        self.download_completed = False
        self.analysis_completed = False
        
        # 初始化设备状态显示
        self.update_device_status("auto")
    
    def clear_previous_data(self):
        """清理之前的数据，释放内存"""
        try:
            # 清理结果数据
            if hasattr(self, 'download_results'):
                self.download_results.clear()
            if hasattr(self, 'analysis_results'):
                self.analysis_results.clear()
            
            # 清理导出器数据
            if hasattr(self, 'exporter') and self.exporter:
                self.exporter.clear_data()
            
            # 清理表格控件
            if hasattr(self, 'result_table'):
                self.result_table.setRowCount(0)
                self.result_table.clearContents()
            
            # 清理统计信息
            if hasattr(self, 'stats_text'):
                self.stats_text.clear()
            
            # 强制垃圾回收
            gc.collect()
            
            # 如果有CUDA，清理GPU缓存
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
                
            self.log_message("已清理之前的数据，释放内存")
            
        except Exception as e:
            self.log_message(f"清理数据时出错: {e}")
    
    def clear_memory_periodically(self):
        """定期清理内存（在处理大量数据时调用）"""
        try:
            # 强制垃圾回收
            gc.collect()
            
            # 清理GPU缓存
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
                
        except Exception as e:
            print(f"定期内存清理失败: {e}")
    
    def init_ui(self):
        """初始化用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 创建左侧控制面板
        control_panel = self.create_control_panel()
        
        # 创建右侧结果显示区
        result_panel = self.create_result_panel()
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(control_panel)
        splitter.addWidget(result_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
        
        # 添加状态栏和内存监控
        self.init_status_bar()

    def init_status_bar(self):
        """初始化状态栏和内存监控"""
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        
        # 内存监控标签
        self.memory_label = QLabel("内存: 0 MB")
        self.status_bar.addPermanentWidget(self.memory_label)
        
        # 内存监控定时器
        self.memory_timer = QTimer()
        self.memory_timer.timeout.connect(self.update_memory_info)
        self.memory_timer.start(5000)  # 每5秒更新一次内存信息
    
    def update_memory_info(self):
        """更新内存使用信息"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self.memory_label.setText(f"内存: {memory_mb:.1f} MB")
            
            # 如果内存使用超过阈值，自动清理
            if memory_mb > 1000:  # 超过1GB时自动清理
                self.clear_memory_periodically()
                # self.log_message(f"内存使用过高({memory_mb:.1f}MB)，已自动清理")
        except ImportError:
            # 如果没有psutil，使用gc模块的简单监控
            import gc
            self.memory_label.setText(f"对象数: {len(gc.get_objects())}")
        except Exception as e:
            self.memory_label.setText("内存监控异常")

    def create_control_panel(self) -> QWidget:
        """创建左侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # API配置组
        api_group = self.create_api_config_group()
        layout.addWidget(api_group)
        
        # 分析模式选择
        mode_group = self.create_analysis_mode_group()
        layout.addWidget(mode_group)
        
        # 街景下载组（默认显示）
        self.streetview_group = self.create_streetview_group()
        layout.addWidget(self.streetview_group)
        
        # 本地图片分析组（默认隐藏）
        self.local_image_group = self.create_local_image_group()
        layout.addWidget(self.local_image_group)
        
        # 路径配置组
        path_group = self.create_path_config_group()
        layout.addWidget(path_group)
        
        # 参数配置组
        param_group = self.create_parameter_group()
        layout.addWidget(param_group)
        
        # 操作按钮组
        button_group = self.create_button_group()
        layout.addWidget(button_group)
        
        # 进度显示组
        progress_group = self.create_progress_group()
        layout.addWidget(progress_group)
        
        layout.addStretch()
        
        return panel
    
    def create_api_config_group(self) -> QGroupBox:
        """创建API配置组"""
        group = QGroupBox("系统配置")
        layout = QGridLayout(group)
        
        # AK输入
        layout.addWidget(QLabel("Access Key (AK):"), 0, 0)
        self.ak_input = QLineEdit()
        self.ak_input.setPlaceholderText("请输入百度地图API的Access Key")
        layout.addWidget(self.ak_input, 0, 1)
        
        # 设备选择
        layout.addWidget(QLabel("计算设备:"), 1, 0)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["自动选择", "强制使用CPU", "强制使用GPU"])
        self.device_combo.setCurrentText("自动选择")
        self.device_combo.currentTextChanged.connect(self.on_device_changed)
        layout.addWidget(self.device_combo, 1, 1)
        
        # 设备状态显示
        self.device_status_label = QLabel("设备状态: 未检测")
        self.device_status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.device_status_label, 2, 0, 1, 2)
        
        # 全景静态图API只需要AK，不需要SK
        
        return group
    
    def create_analysis_mode_group(self) -> QGroupBox:
        """创建分析模式选择组"""
        group = QGroupBox("分析模式")
        layout = QVBoxLayout(group)
        
        # 模式选择单选按钮
        self.streetview_radio = QRadioButton("街景图片下载分析")
        self.local_image_radio = QRadioButton("本地图片分析")
        
        # 默认选择街景模式
        self.streetview_radio.setChecked(True)
        
        # 连接信号
        self.streetview_radio.toggled.connect(self.on_mode_changed)
        self.local_image_radio.toggled.connect(self.on_mode_changed)
        
        layout.addWidget(self.streetview_radio)
        layout.addWidget(self.local_image_radio)
        
        return group
    
    def create_local_image_group(self) -> QGroupBox:
        """创建本地图片分析组"""
        group = QGroupBox("本地图片选择")
        layout = QVBoxLayout(group)
        
        # 单个图片选择
        single_layout = QHBoxLayout()
        single_layout.addWidget(QLabel("单个图片:"))
        self.single_image_input = QLineEdit()
        self.single_image_input.setPlaceholderText("选择单个图片文件")
        single_browse_btn = QPushButton("浏览")
        single_browse_btn.clicked.connect(self.browse_single_image)
        single_layout.addWidget(self.single_image_input)
        single_layout.addWidget(single_browse_btn)
        layout.addLayout(single_layout)
        
        # 文件夹选择
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("图片文件夹:"))
        self.image_folder_input = QLineEdit()
        self.image_folder_input.setPlaceholderText("选择包含图片的文件夹")
        folder_browse_btn = QPushButton("浏览")
        folder_browse_btn.clicked.connect(self.browse_image_folder)
        folder_layout.addWidget(self.image_folder_input)
        folder_layout.addWidget(folder_browse_btn)
        layout.addLayout(folder_layout)
        
        # 图片数量显示
        self.image_count_label = QLabel("已选择图片: 0 个")
        layout.addWidget(self.image_count_label)
        
        # 默认隐藏
        group.setVisible(False)
        
        return group
    
    def create_streetview_group(self) -> QGroupBox:
        """创建街景下载组（原坐标输入组）"""
        return self.create_coordinate_input_group()
    
    def create_coordinate_input_group(self) -> QGroupBox:
        """创建坐标输入组"""
        group = QGroupBox("研究区域坐标")
        layout = QVBoxLayout(group)
        
        # 输入方式选择
        input_layout = QHBoxLayout()
        self.coord_input_type = QComboBox()
        self.coord_input_type.addItems(["手动输入", "Excel导入", "自动获取"])
        self.coord_input_type.currentTextChanged.connect(self.on_input_type_changed)
        input_layout.addWidget(QLabel("输入方式:"))
        input_layout.addWidget(self.coord_input_type)
        layout.addLayout(input_layout)
        
        # 手动输入区域
        self.manual_input_widget = QWidget()
        manual_layout = QVBoxLayout(self.manual_input_widget)
        manual_layout.addWidget(QLabel("坐标输入 (每行一个坐标，格式: 经度,纬度):"))
        self.coord_text = QTextEdit()
        self.coord_text.setPlaceholderText("例如:\n116.404,39.915\n121.473,31.230")
        self.coord_text.setMaximumHeight(100)
        manual_layout.addWidget(self.coord_text)
        layout.addWidget(self.manual_input_widget)
        
        # Excel导入区域
        self.excel_input_widget = QWidget()
        excel_layout = QVBoxLayout(self.excel_input_widget)
        
        excel_file_layout = QHBoxLayout()
        self.excel_path_input = QLineEdit()
        self.excel_path_input.setPlaceholderText("选择Excel文件")
        excel_browse_btn = QPushButton("浏览")
        excel_browse_btn.clicked.connect(self.browse_excel_file)
        excel_file_layout.addWidget(self.excel_path_input)
        excel_file_layout.addWidget(excel_browse_btn)
        excel_layout.addLayout(excel_file_layout)
        
        # 列名配置
        col_layout = QHBoxLayout()
        col_layout.addWidget(QLabel("经度列:"))
        self.lng_col_input = QLineEdit("lon")
        col_layout.addWidget(self.lng_col_input)
        col_layout.addWidget(QLabel("纬度列:"))
        self.lat_col_input = QLineEdit("lat")
        col_layout.addWidget(self.lat_col_input)
        excel_layout.addLayout(col_layout)
        
        self.excel_input_widget.setVisible(False)
        layout.addWidget(self.excel_input_widget)
        
        # 自动获取区域
        self.auto_collect_widget = QWidget()
        auto_layout = QVBoxLayout(self.auto_collect_widget)
        
        # 区域选择
        region_layout = QHBoxLayout()
        region_layout.addWidget(QLabel("目标区域:"))
        self.region_input = QLineEdit()
        self.region_input.setPlaceholderText("例如: 北京市, 上海市, 广州市")
        region_layout.addWidget(self.region_input)
        auto_layout.addLayout(region_layout)
        
        # POI类型选择
        poi_layout = QVBoxLayout()
        poi_layout.addWidget(QLabel("感兴趣区域类型:"))
        
        # 创建POI类型复选框
        poi_grid = QGridLayout()
        self.poi_checkboxes = {}
        poi_types = ["学校", "医院", "政府单位", "公园", "商场", "银行", "酒店", "餐厅", "加油站", "地铁站"]
        
        for i, poi_type in enumerate(poi_types):
            checkbox = QCheckBox(poi_type)
            self.poi_checkboxes[poi_type] = checkbox
            poi_grid.addWidget(checkbox, i // 3, i % 3)
        
        poi_layout.addLayout(poi_grid)
        auto_layout.addLayout(poi_layout)
        
        # 额外关键词
        keyword_layout = QHBoxLayout()
        keyword_layout.addWidget(QLabel("额外关键词:"))
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("可选，用逗号分隔多个关键词")
        keyword_layout.addWidget(self.keyword_input)
        auto_layout.addLayout(keyword_layout)
        
        # 获取数量限制
        limit_layout = QHBoxLayout()
        limit_layout.addWidget(QLabel("每类型最大数量:"))
        self.poi_limit_spin = QSpinBox()
        self.poi_limit_spin.setRange(10, 1000)
        self.poi_limit_spin.setValue(50)
        limit_layout.addWidget(self.poi_limit_spin)
        limit_layout.addStretch()
        auto_layout.addLayout(limit_layout)
        
        self.auto_collect_widget.setVisible(False)
        layout.addWidget(self.auto_collect_widget)
        
        # 解析/获取按钮
        self.coord_action_btn = QPushButton("解析坐标")
        self.coord_action_btn.clicked.connect(self.handle_coordinate_action)
        layout.addWidget(self.coord_action_btn)
        
        # 坐标数量显示
        self.coord_count_label = QLabel("已解析坐标: 0 个")
        layout.addWidget(self.coord_count_label)
        
        return group
    
    def create_path_config_group(self) -> QGroupBox:
        """创建路径配置组"""
        group = QGroupBox("分析文件保存路径")
        layout = QVBoxLayout(group)
        
        path_layout = QHBoxLayout()
        self.save_path_input = QLineEdit()
        self.save_path_input.setPlaceholderText("选择保存目录")
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self.browse_save_directory)
        path_layout.addWidget(self.save_path_input)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        
        return group
    
    def create_parameter_group(self) -> QGroupBox:
        """创建参数配置组"""
        group = QGroupBox("参数配置")
        layout = QGridLayout()
        
        # 图片数量限制
        layout.addWidget(QLabel("图片数量限制:"), 0, 0)
        self.max_images_spin = QSpinBox()
        self.max_images_spin.setRange(1, 10000)
        self.max_images_spin.setValue(100)
        self.max_images_spin.setToolTip("限制下载的图片数量，避免过度消耗资源")
        layout.addWidget(self.max_images_spin, 0, 1)
        
        # 图片尺寸
        layout.addWidget(QLabel("宽度:"), 1, 0)
        self.width_input = QSpinBox()
        self.width_input.setRange(10, 4096)  # 符合API限制[10,4096]
        self.width_input.setValue(1024)
        layout.addWidget(self.width_input, 1, 1)
        
        layout.addWidget(QLabel("高度:"), 1, 2)
        self.height_input = QSpinBox()
        self.height_input.setRange(10, 512)  # 符合API限制[10,512]
        self.height_input.setValue(512)
        layout.addWidget(self.height_input, 1, 3)
        
        # 视野角度
        layout.addWidget(QLabel("视野角度:"), 2, 0)
        self.fov_input = QSpinBox()
        self.fov_input.setRange(10, 360)  # 符合API限制[10,360]
        self.fov_input.setValue(180)  # 默认180度
        layout.addWidget(self.fov_input, 2, 1)
        
        # 俯仰角
        layout.addWidget(QLabel("俯仰角:"), 2, 2)
        self.pitch_input = QSpinBox()
        self.pitch_input.setRange(-90, 90)
        self.pitch_input.setValue(0)
        layout.addWidget(self.pitch_input, 2, 3)
        
        # 坐标类型
        layout.addWidget(QLabel("坐标类型:"), 3, 0)
        self.coordtype_combo = QComboBox()
        self.coordtype_combo.addItems(["wgs84ll (GPS坐标)", "bd09ll (百度坐标)", "gcj02 (谷歌高德坐标)"])
        self.coordtype_combo.setCurrentText("wgs84ll (GPS坐标)")  # 默认GPS坐标
        layout.addWidget(self.coordtype_combo, 3, 1, 1, 2)  # 跨两列
        
        # 内存优化
        layout.addWidget(QLabel("内存优化:"), 4, 0)
        self.memory_optimize_checkbox = QCheckBox("启用内存优化")
        self.memory_optimize_checkbox.setChecked(True)
        self.memory_optimize_checkbox.setToolTip("启用后会在处理过程中自动清理内存，减少内存占用")
        layout.addWidget(self.memory_optimize_checkbox, 4, 1)
        
        # 生成分析图片
        layout.addWidget(QLabel("生成分析图片:"), 4, 2)
        self.generate_images_checkbox = QCheckBox("生成综合分析图片")
        self.generate_images_checkbox.setChecked(True)
        self.generate_images_checkbox.setToolTip("生成包含原图、分割图和植被掩码的综合分析图片")
        layout.addWidget(self.generate_images_checkbox, 4, 3)
        
        group.setLayout(layout)
        return group
    
    def create_button_group(self) -> QGroupBox:
        """创建操作按钮组"""
        group = QGroupBox("操作控制")
        layout = QVBoxLayout(group)
        
        # 加载模型按钮
        self.load_model_btn = QPushButton("加载AI模型")
        self.load_model_btn.clicked.connect(self.load_model)
        layout.addWidget(self.load_model_btn)
        
        # 下载按钮
        self.download_btn = QPushButton("开始下载")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setEnabled(False)
        layout.addWidget(self.download_btn)
        
        # 分析按钮
        self.analyze_btn = QPushButton("开始分析")
        self.analyze_btn.clicked.connect(self.start_analysis)
        self.analyze_btn.setEnabled(False)
        layout.addWidget(self.analyze_btn)
        
        # 导出按钮
        self.export_btn = QPushButton("导出报表")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)
        
        # 取消按钮
        self.cancel_btn = QPushButton("取消任务")
        self.cancel_btn.clicked.connect(self.cancel_task)
        self.cancel_btn.setEnabled(False)
        layout.addWidget(self.cancel_btn)
        
        return group
    
    def create_progress_group(self) -> QGroupBox:
        """创建进度显示组"""
        group = QGroupBox("任务进度")
        layout = QVBoxLayout(group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
        return group
    
    def create_result_panel(self) -> QWidget:
        """创建右侧结果显示面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # 日志标签页
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.tab_widget.addTab(self.log_text, "运行日志")
        
        # 结果表格标签页
        self.result_table = QTableWidget()
        self.tab_widget.addTab(self.result_table, "分析结果")
        
        # 统计信息标签页
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.tab_widget.addTab(self.stats_text, "统计信息")
        
        layout.addWidget(self.tab_widget)
        
        return panel
    
    def init_style(self):
        """初始化样式"""
        # 设置应用程序样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                text-align: center;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QLineEdit, QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                font-size: 12px;
            }
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
    
    def on_input_type_changed(self, input_type: str):
        """输入方式改变事件"""
        # 隐藏所有输入组件
        self.manual_input_widget.setVisible(False)
        self.excel_input_widget.setVisible(False)
        self.auto_collect_widget.setVisible(False)
        
        # 根据选择显示对应组件
        if input_type == "手动输入":
            self.manual_input_widget.setVisible(True)
            self.coord_action_btn.setText("解析坐标")
        elif input_type == "Excel导入":
            self.excel_input_widget.setVisible(True)
            self.coord_action_btn.setText("解析坐标")
        elif input_type == "自动获取":
            self.auto_collect_widget.setVisible(True)
            self.coord_action_btn.setText("获取坐标")
    
    def browse_excel_file(self):
        """浏览Excel文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Excel文件", "", "Excel文件 (*.xlsx *.xls)"
        )
        if file_path:
            self.excel_path_input.setText(file_path)
    
    def browse_save_directory(self):
        """浏览保存目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if directory:
            self.save_path_input.setText(directory)
            self.current_save_dir = directory
    
    def handle_coordinate_action(self):
        """处理坐标操作（解析或获取）"""
        input_type = self.coord_input_type.currentText()
        
        if input_type == "自动获取":
            self.auto_collect_coordinates()
        else:
            self.parse_coordinates()
    
    def auto_collect_coordinates(self):
        """自动获取坐标"""
        try:
            # 检查区域输入
            region = self.region_input.text().strip()
            if not region:
                QMessageBox.warning(self, "警告", "请输入目标区域")
                return
            
            # 检查POI类型选择
            selected_poi_types = []
            for poi_type, checkbox in self.poi_checkboxes.items():
                if checkbox.isChecked():
                    selected_poi_types.append(poi_type)
            
            if not selected_poi_types:
                QMessageBox.warning(self, "警告", "请至少选择一种POI类型")
                return
            
            # 检查API密钥
            api_key = self.ak_input.text().strip()
            if not api_key:
                QMessageBox.warning(self, "警告", "请输入百度地图API密钥")
                return
            
            # 设置API密钥
            self.coordinate_collector.set_api_key(api_key)
            
            # 获取额外关键词
            keywords = []
            keyword_text = self.keyword_input.text().strip()
            if keyword_text:
                keywords = [k.strip() for k in keyword_text.split(',') if k.strip()]
            
            # 获取数量限制
            limit = self.poi_limit_spin.value()
            
            # 禁用按钮，显示进度
            self.coord_action_btn.setEnabled(False)
            self.coord_action_btn.setText("正在获取...")
            
            self.log_message(f"开始自动获取坐标: 区域={region}, POI类型={selected_poi_types}")
            
            # 批量收集坐标
            df = self.coordinate_collector.batch_collect_coordinates(
                regions=[region],
                poi_types=selected_poi_types,
                keywords=keywords,
                limit_per_type=limit
            )
            
            if df is not None and not df.empty:
                # 转换为坐标列表
                self.coordinates = [(row['longitude'], row['latitude']) for _, row in df.iterrows()]
                
                # 更新坐标数量显示
                self.coord_count_label.setText(f"已获取坐标: {len(self.coordinates)} 个")
                
                # 启用下载按钮
                if len(self.coordinates) > 0 and self.ak_input.text().strip():
                    self.download_btn.setEnabled(True)
                
                self.log_message(f"成功获取 {len(self.coordinates)} 个坐标")
                
                # 询问是否保存坐标到文件
                reply = QMessageBox.question(
                    self, "保存坐标", 
                    f"成功获取 {len(self.coordinates)} 个坐标，是否保存到Excel文件？",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    from PyQt5.QtWidgets import QFileDialog
                    file_path, _ = QFileDialog.getSaveFileName(
                        self, "保存坐标文件", 
                        f"{region}_坐标.xlsx",
                        "Excel文件 (*.xlsx)"
                    )
                    
                    if file_path:
                        self.coordinate_collector.save_coordinates(df, file_path)
                        self.log_message(f"坐标已保存到: {file_path}")
            else:
                QMessageBox.information(self, "提示", "未找到符合条件的坐标")
                self.log_message("未找到符合条件的坐标")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"自动获取坐标失败: {str(e)}")
            self.log_message(f"自动获取坐标失败: {str(e)}")
        
        finally:
            # 恢复按钮状态
            self.coord_action_btn.setEnabled(True)
            self.coord_action_btn.setText("获取坐标")
    
    def parse_coordinates(self):
        """解析坐标"""
        try:
            if self.coord_input_type.currentText() == "手动输入":
                coord_text = self.coord_text.toPlainText()
                if not coord_text.strip():
                    QMessageBox.warning(self, "警告", "请输入坐标数据")
                    return
                
                # 创建临时收集器来解析坐标
                temp_collector = BaiduStreetViewCollector("temp")
                self.coordinates = temp_collector.parse_coordinates(coord_text)
                
            else:  # Excel导入
                excel_path = self.excel_path_input.text()
                if not excel_path:
                    QMessageBox.warning(self, "警告", "请选择Excel文件")
                    return
                
                lng_col = self.lng_col_input.text()
                lat_col = self.lat_col_input.text()
                
                temp_collector = BaiduStreetViewCollector("temp")
                self.coordinates = temp_collector.parse_excel_coordinates(
                    excel_path, lng_col, lat_col
                )
            
            # 更新坐标数量显示
            self.coord_count_label.setText(f"已解析坐标: {len(self.coordinates)} 个")
            
            # 启用下载按钮
            if len(self.coordinates) > 0 and self.ak_input.text().strip():
                self.download_btn.setEnabled(True)
            
            self.log_message(f"成功解析 {len(self.coordinates)} 个坐标")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"解析坐标失败: {str(e)}")
            self.log_message(f"解析坐标失败: {str(e)}")
    
    def load_model(self):
        """加载AI模型"""
        try:
            print(f"🔧 load_model函数被调用")
            self.log_message("开始加载AI模型...")
            self.load_model_btn.setEnabled(False)
            self.load_model_btn.setText("加载中...")
            
            # 获取用户选择的设备
            device_text = self.device_combo.currentText()
            print(f"🔧 load_model读取的设备选择: {device_text}")
            device_map = {
                "自动选择": "auto",
                "强制使用CPU": "cpu",
                "强制使用GPU": "cuda"
            }
            selected_device = device_map.get(device_text, "auto")
            print(f"🔧 load_model映射后的设备: {selected_device}")
            
            # 在后台线程中加载模型
            def load_model_thread():
                try:
                    # 使用用户选择的设备初始化分析器
                    self.analyzer = GreenViewAnalyzer(device=selected_device)
                    success = self.analyzer.load_model()
                    
                    if success:
                        self.model_loaded = True
                        device_info = f"AI模型加载成功 (设备: {self.analyzer.device})"
                        self.log_message(device_info)
                        self.load_model_btn.setText(f"模型已加载 ({self.analyzer.device.upper()})")
                        
                        # 更新设备状态显示（显示实际使用的设备）
                        actual_device = self.analyzer.device
                        if actual_device == "cuda":
                            try:
                                import torch
                                device_name = torch.cuda.get_device_name(0)
                                self.device_status_label.setText(f"设备状态: 使用GPU - {device_name}")
                                self.device_status_label.setStyleSheet("color: #2E8B57; font-size: 12px;")
                            except:
                                self.device_status_label.setText("设备状态: 使用GPU")
                                self.device_status_label.setStyleSheet("color: #2E8B57; font-size: 12px;")
                        else:
                            self.device_status_label.setText("设备状态: 使用CPU")
                            self.device_status_label.setStyleSheet("color: #4169E1; font-size: 12px;")
                        
                        # 检查是否可以启用分析按钮
                        if self.streetview_radio.isChecked():
                            # 街景模式：需要下载完成
                            if self.download_completed:
                                self.analyze_btn.setEnabled(True)
                        else:
                            # 本地图片模式：需要选择了图片路径
                            image_paths = self.get_local_image_paths()
                            if image_paths:
                                self.analyze_btn.setEnabled(True)
                    else:
                        self.log_message("AI模型加载失败")
                        self.load_model_btn.setEnabled(True)
                        self.load_model_btn.setText("加载AI模型")
                        
                except Exception as e:
                    self.log_message(f"加载模型时出错: {str(e)}")
                    self.load_model_btn.setEnabled(True)
                    self.load_model_btn.setText("加载AI模型")
            
            # 启动加载线程
            threading.Thread(target=load_model_thread, daemon=True).start()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载模型失败: {str(e)}")
    
    def start_download(self):
        """开始下载"""
        try:
            # 验证输入
            ak = self.ak_input.text().strip()
            if not ak:
                QMessageBox.warning(self, "警告", "请输入百度地图API的Access Key")
                return
            
            if not self.coordinates:
                QMessageBox.warning(self, "警告", "请先解析坐标")
                return
            
            if not self.current_save_dir:
                QMessageBox.warning(self, "警告", "请选择保存目录")
                return
            
            # 清理旧数据，释放内存
            self.clear_previous_data()
            
            # 创建收集器（全景静态图API只需要AK）
            self.collector = BaiduStreetViewCollector(ak)
            
            # 创建图片保存目录
            images_dir = os.path.join(self.current_save_dir, "images")
            os.makedirs(images_dir, exist_ok=True)
            
            # 获取图片参数
            width = self.width_input.value()
            height = self.height_input.value()
            fov = self.fov_input.value()
            pitch = self.pitch_input.value()
            
            # 获取坐标类型
            coordtype_text = self.coordtype_combo.currentText()
            coordtype = coordtype_text.split(' ')[0]  # 提取坐标类型代码（如bd09ll）
            
            # 启动下载线程
            self.worker_thread = WorkerThread(
                "download",
                collector=self.collector,
                coordinates=self.coordinates,
                save_dir=images_dir,
                width=width,
                height=height,
                fov=fov,
                pitch=pitch,
                coordtype=coordtype
            )
            
            self.worker_thread.progress_updated.connect(self.update_progress)
            self.worker_thread.task_completed.connect(self.on_task_completed)
            self.worker_thread.analysis_results_ready.connect(self.on_analysis_results_ready)
            self.worker_thread.error_occurred.connect(self.on_error_occurred)
            
            self.worker_thread.start()
            
            # 更新UI状态
            self.download_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
            self.log_message(f"开始下载 {len(self.coordinates)} 张街景图片...")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动下载失败: {str(e)}")
    
    def start_analysis(self):
        """开始分析"""
        try:
            if not self.model_loaded:
                QMessageBox.warning(self, "警告", "请先加载AI模型")
                return
            
            image_paths = []
            
            if self.streetview_radio.isChecked():
                # 街景模式：检查下载完成状态
                if not self.download_completed:
                    QMessageBox.warning(self, "警告", "请先完成图片下载")
                    return
                
                # 获取已下载的图片路径
                for result in self.download_results:
                    if result['success'] and result.get('filepath'):
                        image_paths.append(result['filepath'])
                
                if not image_paths:
                    QMessageBox.warning(self, "警告", "没有找到已下载的图片")
                    return
            else:
                # 本地图片模式：获取本地图片路径
                image_paths = self.get_local_image_paths()
                
                if not image_paths:
                    QMessageBox.warning(self, "警告", "请选择要分析的图片或图片文件夹")
                    return
            
            # 确保保存目录存在
            if not self.current_save_dir:
                QMessageBox.warning(self, "警告", "请先设置保存目录")
                return
            
            # 清理旧数据，释放内存
            self.clear_previous_data()
            
            # 启动分析线程（不创建analysis文件夹，直接使用当前保存目录）
            self.worker_thread = WorkerThread(
                "analyze",
                analyzer=self.analyzer,
                image_paths=image_paths,
                output_dir=self.current_save_dir,
                exporter=self.exporter,  # 传递导出器实例
                generate_images=self.generate_images_checkbox.isChecked()  # 传递复选框状态
            )
            
            self.worker_thread.progress_updated.connect(self.update_progress)
            self.worker_thread.task_completed.connect(self.on_task_completed)
            self.worker_thread.analysis_results_ready.connect(self.on_analysis_results_ready)
            self.worker_thread.error_occurred.connect(self.on_error_occurred)
            
            self.worker_thread.start()
            
            # 更新UI状态
            self.analyze_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
            
            mode_text = "街景图片" if self.streetview_radio.isChecked() else "本地图片"
            self.log_message(f"开始分析 {len(image_paths)} 张{mode_text}的绿视率...")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动分析失败: {str(e)}")
    
    def export_results(self):
        """导出结果"""
        try:
            if not self.analysis_completed:
                QMessageBox.warning(self, "警告", "请先完成图片分析")
                return
            
            # 选择导出文件路径
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存报表", 
                os.path.join(self.current_save_dir, "绿视率分析报表.xlsx"),
                "Excel文件 (*.xlsx)"
            )
            
            if not file_path:
                return
            
            # 启动导出线程
            self.worker_thread = WorkerThread(
                "export",
                exporter=self.exporter,
                output_path=file_path
            )
            
            self.worker_thread.task_completed.connect(self.on_task_completed)
            self.worker_thread.error_occurred.connect(self.on_error_occurred)
            
            self.worker_thread.start()
            
            # 更新UI状态
            self.export_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
            self.log_message(f"开始导出报表到: {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    def cancel_task(self):
        """取消当前任务"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.cancel()
            self.worker_thread.wait()
            self.log_message("任务已取消")
            self.reset_ui_state()
    
    def update_progress(self, current: int, total: int, message: str):
        """更新进度"""
        progress = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)
        self.log_message(message)
    
    def on_task_completed(self, task_type: str, success: bool):
        """任务完成事件"""
        if task_type == "download":
            self.download_results = self.collector.download_records
            self.download_completed = True
            
            if self.model_loaded:
                self.analyze_btn.setEnabled(True)
            
            summary = self.collector.get_download_summary()
            self.log_message(f"下载完成: 成功 {summary['success']} 张，失败 {summary['failed']} 张")
            
        elif task_type == "analyze":
            self.log_message(f"分析任务完成，成功状态: {success}")
            if success:
                # 分析成功时，保持进度条为100%
                self.progress_bar.setValue(100)
                self.status_label.setText("分析完成")
            else:
                self.log_message("分析任务失败")
            
        elif task_type == "export":
            if success:
                self.log_message("报表导出成功")
                QMessageBox.information(self, "成功", "报表导出成功！")
            else:
                self.log_message("报表导出失败")
                QMessageBox.warning(self, "失败", "报表导出失败")
        
        # 只有在非分析任务或分析失败时才重置UI状态
        if task_type != "analyze" or not success:
            self.reset_ui_state()
        else:
            # 分析成功时只重置按钮状态，保持进度条
            self.cancel_btn.setEnabled(False)
            
            # 根据分析模式重新启用相应按钮
            if self.streetview_radio.isChecked():
                # 街景模式
                if self.coordinates and self.ak_input.text().strip():
                    self.download_btn.setEnabled(True)
                
                if self.model_loaded and self.download_completed:
                    self.analyze_btn.setEnabled(True)
            else:
                # 本地图片模式
                local_paths = self.get_local_image_paths()
                if self.model_loaded and local_paths:
                    self.analyze_btn.setEnabled(True)
            
            if self.analysis_completed:
                self.export_btn.setEnabled(True)
    
    def on_analysis_results_ready(self, results):
        """处理分析结果"""
        self.analysis_results = results
        self.analysis_completed = True
        
        # 调试信息：检查分析结果
        self.log_message(f"收到分析结果: {len(results)} 条")
        if results:
            self.log_message(f"第一条结果示例: {list(results[0].keys()) if results[0] else 'None'}")
            for i, result in enumerate(results[:3]):  # 只显示前3条详细信息
                self.log_message(f"结果 {i+1}: 绿视率={result.get('green_view_rate', 'N/A')}, 图片路径={result.get('image_path', 'N/A')}")
        
        # 根据分析模式更新导出器数据
        if self.streetview_radio.isChecked():
            # 街景模式：使用原有的方法
            self.exporter.add_batch_results(self.download_results, self.analysis_results)
        else:
            # 本地图片模式：使用新的方法
            self.exporter.add_batch_local_results(self.analysis_results)
            
        # 调试信息：检查导出器数据
        self.log_message(f"导出器数据条数: {len(self.exporter.results_data)}")
        if len(self.exporter.results_data) > 0:
            self.log_message(f"导出器第一条数据: {self.exporter.results_data[0]}")
        
        # 综合分析图片已在分析过程中实时生成，无需再次统一生成
        
        self.export_btn.setEnabled(True)
        self.update_result_table()
        self.update_statistics()
        
        self.log_message(f"分析完成: 共分析 {len(self.analysis_results)} 张图片")
    
    def generate_comprehensive_images(self, single_result=None):
        """为分析的图片生成综合分析图片
        
        Args:
            single_result: 单个分析结果，如果提供则只处理这一个结果
        """
        # 确定要处理的结果
        if single_result:
            results_to_process = [single_result]
            batch_mode = False
        else:
            if not self.analysis_results:
                return
            results_to_process = self.analysis_results
            batch_mode = True
            
        try:
            # 创建综合分析图片输出目录
            output_dir = os.path.join(self.save_path_input.text() or 'output', 'comprehensive_analysis')
            os.makedirs(output_dir, exist_ok=True)
            
            if batch_mode:
                self.log_message(f"开始批量生成综合分析图片，输出目录: {output_dir}")
            
            success_count = 0
            total_count = len(results_to_process)
            
            for i, result in enumerate(results_to_process):
                try:
                    # 获取原图文件名（不含扩展名）
                    original_path = result.get('image_path', result.get('original_image_path', ''))
                    if not original_path:
                        continue
                        
                    filename = os.path.splitext(os.path.basename(original_path))[0]
                    output_path = os.path.join(output_dir, f"{filename}_comprehensive_analysis.png")
                    
                    # 生成综合分析图片
                    if self.exporter.generate_comprehensive_analysis_image(result, output_path):
                        success_count += 1
                        if batch_mode:
                            self.log_message(f"已生成综合分析图片 ({i+1}/{total_count}): {filename}")
                        return output_path  # 单张模式返回路径
                    else:
                        if batch_mode:
                            self.log_message(f"生成综合分析图片失败 ({i+1}/{total_count}): {filename}")
                        
                except Exception as e:
                    if batch_mode:
                        self.log_message(f"处理图片时出错: {e}")
                    continue
            
            if batch_mode:
                self.log_message(f"综合分析图片生成完成: 成功 {success_count}/{total_count} 张")
                
                if success_count > 0:
                    QMessageBox.information(self, "成功", 
                                           f"已成功生成 {success_count} 张综合分析图片\n保存位置: {output_dir}")
            
        except Exception as e:
            self.log_message(f"生成综合分析图片时出错: {e}")
            if batch_mode:
                QMessageBox.warning(self, "警告", f"生成综合分析图片时出错: {e}")
            
        return None
    

    
    def on_error_occurred(self, error_message: str):
        """错误发生事件"""
        self.log_message(f"错误: {error_message}")
        QMessageBox.critical(self, "错误", error_message)
        self.reset_ui_state()
    
    def reset_ui_state(self):
        """重置UI状态"""
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("就绪")
        
        # 根据分析模式重新启用相应按钮
        if self.streetview_radio.isChecked():
            # 街景模式
            if self.coordinates and self.ak_input.text().strip():
                self.download_btn.setEnabled(True)
            
            if self.model_loaded and self.download_completed:
                self.analyze_btn.setEnabled(True)
        else:
            # 本地图片模式
            local_paths = self.get_local_image_paths()
            if self.model_loaded and local_paths:
                self.analyze_btn.setEnabled(True)
        
        if self.analysis_completed:
            self.export_btn.setEnabled(True)
    
    def update_result_table(self):
        """更新结果表格（限制显示数量以节省内存）"""
        if not self.analysis_results:
            return

        # 限制表格显示的最大行数，避免内存过度占用
        max_display_rows = 1000
        display_results = self.analysis_results[:max_display_rows]
        
        if len(self.analysis_results) > max_display_rows:
            self.log_message(f"结果过多，仅显示前 {max_display_rows} 条结果")

        if self.streetview_radio.isChecked():
            # 街景模式：显示经纬度
            self.result_table.setColumnCount(5)
            headers = ["经度", "纬度", "绿视率(%)", "植被像素", "总像素"]
            self.result_table.setHorizontalHeaderLabels(headers)
            self.result_table.setRowCount(len(display_results))
            
            # 填充数据
            for i, result in enumerate(display_results):
                # 从对应的下载结果中获取坐标
                download_result = self.download_results[i] if i < len(self.download_results) else {}
                
                self.result_table.setItem(i, 0, QTableWidgetItem(str(download_result.get('lng', ''))))
                self.result_table.setItem(i, 1, QTableWidgetItem(str(download_result.get('lat', ''))))
                self.result_table.setItem(i, 2, QTableWidgetItem(f"{result.get('green_view_rate', 0):.2f}"))
                self.result_table.setItem(i, 3, QTableWidgetItem(str(result.get('vegetation_pixels', 0))))
                self.result_table.setItem(i, 4, QTableWidgetItem(str(result.get('total_pixels', 0))))
        else:
            # 本地图片模式：显示文件名
            self.result_table.setColumnCount(4)
            headers = ["图片文件名", "绿视率(%)", "植被像素", "总像素"]
            self.result_table.setHorizontalHeaderLabels(headers)
            self.result_table.setRowCount(len(display_results))
            
            # 填充数据
            for i, result in enumerate(display_results):
                import os
                image_path = result.get('image_path', '')
                filename = os.path.basename(image_path) if image_path else f"图片_{i+1}"
                
                self.result_table.setItem(i, 0, QTableWidgetItem(filename))
                self.result_table.setItem(i, 1, QTableWidgetItem(f"{result.get('green_view_rate', 0):.2f}"))
                self.result_table.setItem(i, 2, QTableWidgetItem(str(result.get('vegetation_pixels', 0))))
                self.result_table.setItem(i, 3, QTableWidgetItem(str(result.get('total_pixels', 0))))
        
        # 调整列宽
        self.result_table.resizeColumnsToContents()
        
        # 清理内存
        self.clear_memory_periodically()
    
    def update_statistics(self):
        """更新统计信息"""
        stats = self.exporter.calculate_summary_statistics()
        
        stats_text = f"""
统计汇总报告
{'='*50}

基本信息:
- 总图片数: {stats.get('total_images', 0)} 张
- 下载成功: {stats.get('successful_downloads', 0)} 张
- 分析成功: {stats.get('successful_analyses', 0)} 张
- 下载成功率: {stats.get('download_success_rate', 0):.2f}%
- 分析成功率: {stats.get('analysis_success_rate', 0):.2f}%

绿视率统计:
- 平均值: {stats.get('green_view_rate_mean', 0):.2f}%
- 中位数: {stats.get('green_view_rate_median', 0):.2f}%
- 标准差: {stats.get('green_view_rate_std', 0):.2f}%
- 最小值: {stats.get('green_view_rate_min', 0):.2f}%
- 最大值: {stats.get('green_view_rate_max', 0):.2f}%
- 25%分位数: {stats.get('green_view_rate_q25', 0):.2f}%
- 75%分位数: {stats.get('green_view_rate_q75', 0):.2f}%

绿视率分布:
"""
        
        if 'green_view_distribution' in stats:
            for level, count in stats['green_view_distribution'].items():
                stats_text += f"- {level}: {count} 张\n"
        
        self.stats_text.setPlainText(stats_text)
    
    def on_mode_changed(self):
        """分析模式切换处理"""
        if self.streetview_radio.isChecked():
            # 显示街景下载组，隐藏本地图片组
            self.streetview_group.setVisible(True)
            self.local_image_group.setVisible(False)
            # 更新按钮状态
            self.download_btn.setVisible(True)
            self.download_btn.setText("开始下载")
            self.analyze_btn.setText("开始分析")
            
            # 重置状态并更新按钮启用状态
            self.download_completed = False
            self.analysis_completed = False
            self.download_btn.setEnabled(bool(self.coordinates and self.ak_input.text().strip()))
            self.analyze_btn.setEnabled(False)
            self.export_btn.setEnabled(False)
        else:
            # 隐藏街景下载组，显示本地图片组
            self.streetview_group.setVisible(False)
            self.local_image_group.setVisible(True)
            # 更新按钮状态
            self.download_btn.setVisible(False)
            self.analyze_btn.setText("分析本地图片")
            
            # 重置状态并更新按钮启用状态
            self.analysis_completed = False
            local_paths = self.get_local_image_paths()
            self.analyze_btn.setEnabled(bool(self.model_loaded and local_paths))
            self.export_btn.setEnabled(False)
        
        # 清空结果显示
        self.result_table.setRowCount(0)
        self.stats_text.clear()
        self.log_text.clear()
        
        # 清空导出器数据
        self.exporter.clear_data()
    
    def reload_model_with_device(self, device: str):
        """重新加载模型到指定设备"""
        try:
            self.log_message(f"正在切换设备到: {device}")
            self.load_model_btn.setEnabled(False)
            self.load_model_btn.setText("切换设备中...")
            
            # 在后台线程中重新加载模型
            def reload_thread():
                try:
                    # 使用指定设备重新初始化分析器
                    self.analyzer = GreenViewAnalyzer(device=device)
                    success = self.analyzer.load_model()
                    
                    if success:
                        self.model_loaded = True
                        device_info = f"模型已切换到设备: {self.analyzer.device}"
                        self.log_message(device_info)
                        self.load_model_btn.setText(f"模型已加载 ({self.analyzer.device.upper()})")
                        
                        # 更新设备状态显示
                        actual_device = self.analyzer.device
                        if actual_device == "cuda":
                            try:
                                import torch
                                device_name = torch.cuda.get_device_name(0)
                                self.device_status_label.setText(f"设备状态: 使用GPU - {device_name}")
                                self.device_status_label.setStyleSheet("color: #2E8B57; font-size: 12px;")
                            except:
                                self.device_status_label.setText("设备状态: 使用GPU")
                                self.device_status_label.setStyleSheet("color: #2E8B57; font-size: 12px;")
                        else:
                            self.device_status_label.setText("设备状态: 使用CPU")
                            self.device_status_label.setStyleSheet("color: #4169E1; font-size: 12px;")
                        
                        print(f"✅ 设备切换成功: {actual_device}")
                    else:
                        self.log_message("模型重新加载失败")
                        self.load_model_btn.setText("重新加载失败")
                        print("❌ 模型重新加载失败")
                        
                except Exception as e:
                    self.log_message(f"设备切换失败: {str(e)}")
                    self.load_model_btn.setText("切换失败")
                    print(f"❌ 设备切换异常: {e}")
                finally:
                    self.load_model_btn.setEnabled(True)
            
            # 启动后台线程
            import threading
            thread = threading.Thread(target=reload_thread)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            self.log_message(f"设备切换启动失败: {str(e)}")
            self.load_model_btn.setEnabled(True)
            print(f"❌ 设备切换启动失败: {e}")

    def on_device_changed(self, device_text: str):
        """设备选择变化处理"""
        print(f"🔧 设备选择回调被触发: {device_text}")
        
        # 将界面文本转换为内部设备标识
        device_map = {
            "自动选择": "auto",
            "强制使用CPU": "cpu", 
            "强制使用GPU": "cuda"
        }
        
        selected_device = device_map.get(device_text, "auto")
        print(f"🔧 映射后的设备: {selected_device}")
        
        # 检测设备状态并更新显示
        self.update_device_status(selected_device)
        
        print(f"🔧 当前状态检查: analyzer={self.analyzer is not None}, model_loaded={self.model_loaded}")
        
        # 如果分析器已经初始化且模型已加载，重新加载模型到新设备
        if self.analyzer is not None and self.model_loaded:
            try:
                print(f"设备切换中: {device_text} -> {selected_device}")
                self.model_loaded = False  # 标记需要重新加载模型
                
                # 重新加载模型到新设备
                self.reload_model_with_device(selected_device)
                print(f"设备已切换到: {selected_device}，正在重新加载模型...")
                
            except Exception as e:
                print(f"设备切换失败: {e}")
                self.device_status_label.setText(f"设备状态: 切换失败 - {str(e)}")
        elif self.analyzer is not None:
            # 如果分析器存在但模型未加载，只切换设备
            try:
                self.analyzer = GreenViewAnalyzer(device=selected_device)
                print(f"设备已切换到: {selected_device}")
            except Exception as e:
                print(f"设备切换失败: {e}")
                self.device_status_label.setText(f"设备状态: 切换失败 - {str(e)}")
    
    def update_device_status(self, device_preference: str = "auto"):
        """更新设备状态显示"""
        try:
            import torch
            
            # 检测CUDA可用性
            cuda_available = torch.cuda.is_available()
            
            if device_preference == "auto":
                if cuda_available:
                    try:
                        # 测试CUDA设备
                        test_tensor = torch.tensor([1.0]).cuda()
                        device_name = torch.cuda.get_device_name(0)
                        self.device_status_label.setText(f"设备状态: 自动选择 - GPU ({device_name})")
                        self.device_status_label.setStyleSheet("color: #2E8B57; font-size: 12px;")
                    except Exception:
                        self.device_status_label.setText("设备状态: 自动选择 - CPU (GPU测试失败)")
                        self.device_status_label.setStyleSheet("color: #FF8C00; font-size: 12px;")
                else:
                    self.device_status_label.setText("设备状态: 自动选择 - CPU (无GPU)")
                    self.device_status_label.setStyleSheet("color: #4169E1; font-size: 12px;")
            
            elif device_preference == "cpu":
                self.device_status_label.setText("设备状态: 强制使用CPU")
                self.device_status_label.setStyleSheet("color: #4169E1; font-size: 12px;")
            
            elif device_preference == "cuda":
                if cuda_available:
                    try:
                        # 测试CUDA设备
                        test_tensor = torch.tensor([1.0]).cuda()
                        device_name = torch.cuda.get_device_name(0)
                        self.device_status_label.setText(f"设备状态: 强制使用GPU - {device_name}")
                        self.device_status_label.setStyleSheet("color: #2E8B57; font-size: 12px;")
                    except Exception as e:
                        self.device_status_label.setText(f"设备状态: GPU不可用，将回退到CPU - {str(e)}")
                        self.device_status_label.setStyleSheet("color: #FF8C00; font-size: 12px;")
                else:
                    self.device_status_label.setText("设备状态: GPU不可用，将回退到CPU")
                    self.device_status_label.setStyleSheet("color: #FF8C00; font-size: 12px;")
        
        except ImportError:
            self.device_status_label.setText("设备状态: PyTorch未安装")
            self.device_status_label.setStyleSheet("color: #DC143C; font-size: 12px;")
        except Exception as e:
            self.device_status_label.setText(f"设备状态: 检测失败 - {str(e)}")
            self.device_status_label.setStyleSheet("color: #DC143C; font-size: 12px;")
    
    def browse_single_image(self):
        """浏览选择单个图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片文件", "", 
            "图片文件 (*.jpg *.jpeg *.png *.bmp *.tiff);;所有文件 (*)"
        )
        
        if file_path:
            self.single_image_input.setText(file_path)
            self.image_folder_input.clear()  # 清空文件夹选择
            self.update_local_image_count()
            # 更新分析按钮状态
            if self.model_loaded:
                self.analyze_btn.setEnabled(True)
    
    def browse_image_folder(self):
        """浏览选择图片文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择图片文件夹", ""
        )
        
        if folder_path:
            self.image_folder_input.setText(folder_path)
            self.single_image_input.clear()  # 清空单个图片选择
            self.update_local_image_count()
            # 更新分析按钮状态
            local_paths = self.get_local_image_paths()
            if self.model_loaded and local_paths:
                self.analyze_btn.setEnabled(True)
    
    def update_local_image_count(self):
        """更新本地图片数量显示"""
        import os
        count = 0
        
        # 支持的图片格式
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        
        if self.single_image_input.text().strip():
            # 单个文件
            file_path = self.single_image_input.text().strip()
            if os.path.isfile(file_path):
                ext = os.path.splitext(file_path)[1].lower()
                if ext in image_extensions:
                    count = 1
        elif self.image_folder_input.text().strip():
            # 文件夹
            folder_path = self.image_folder_input.text().strip()
            if os.path.isdir(folder_path):
                for file_name in os.listdir(folder_path):
                    ext = os.path.splitext(file_name)[1].lower()
                    if ext in image_extensions:
                        count += 1
        
        self.image_count_label.setText(f"已选择图片: {count} 个")
        
        # 更新分析按钮状态
        if self.local_image_radio.isChecked() and self.model_loaded and count > 0:
            self.analyze_btn.setEnabled(True)
        elif self.local_image_radio.isChecked():
            self.analyze_btn.setEnabled(False)
    
    def get_local_image_paths(self):
        """获取本地图片路径列表"""
        import os
        image_paths = []
        
        # 支持的图片格式
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        
        if self.single_image_input.text().strip():
            # 单个文件
            file_path = self.single_image_input.text().strip()
            if os.path.isfile(file_path):
                ext = os.path.splitext(file_path)[1].lower()
                if ext in image_extensions:
                    image_paths.append(file_path)
        elif self.image_folder_input.text().strip():
            # 文件夹
            folder_path = self.image_folder_input.text().strip()
            if os.path.isdir(folder_path):
                for file_name in os.listdir(folder_path):
                    ext = os.path.splitext(file_name)[1].lower()
                    if ext in image_extensions:
                        image_paths.append(os.path.join(folder_path, file_name))
        
        return image_paths
    
    def log_message(self, message: str):
        """记录日志消息"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_text.append(log_entry)
        
        # 自动滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        self.log_text.setTextCursor(cursor)

# 测试函数
def test_gui():
    """测试GUI界面"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    test_gui()