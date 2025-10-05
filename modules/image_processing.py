#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图像处理模块 - SegFormer模型加载和语义分割

功能：
1. 加载SegFormer预训练模型
2. 对街景图片进行语义分割
3. 提取植被区域并计算绿视率
4. 生成分析结果图片
"""

import os
import torch
import numpy as np
from PIL import Image
import cv2
import gc  # 添加垃圾回收模块
import tempfile
import shutil
from typing import Tuple, Dict, Optional, List
from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation
import warnings
warnings.filterwarnings('ignore')

class GreenViewAnalyzer:
    """绿视率分析器"""
    
    # Cityscapes数据集类别映射
    CITYSCAPES_CLASSES = {
        0: 'road', 1: 'sidewalk', 2: 'building', 3: 'wall', 4: 'fence',
        5: 'pole', 6: 'traffic_light', 7: 'traffic_sign', 8: 'vegetation',
        9: 'terrain', 10: 'sky', 11: 'person', 12: 'rider', 13: 'car',
        14: 'truck', 15: 'bus', 16: 'train', 17: 'motorcycle', 18: 'bicycle'
    }
    
    # 植被类别ID（在Cityscapes中vegetation的ID是8）
    VEGETATION_CLASS_ID = 8
    
    def __init__(self, model_name: str = "nvidia/segformer-b5-finetuned-cityscapes-1024-1024", 
                 device: Optional[str] = None):
        """
        初始化分析器
        
        Args:
            model_name: 模型名称
            device: 计算设备 ('cpu', 'cuda', 'auto')
        """
        self.model_name = model_name
        self.device = self._get_device(device)
        self.processor = None
        self.model = None
        self.model_loaded = False
        
        print(f"使用设备: {self.device}")
    
    def _cleanup_memory(self):
        """清理内存和GPU缓存"""
        try:
            # 多次强制垃圾回收
            for _ in range(3):
                gc.collect()
            
            # 如果使用CUDA，清空GPU缓存
            if self.device == 'cuda' and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()  # 同步CUDA操作
                # 额外的GPU内存清理
                if hasattr(torch.cuda, 'ipc_collect'):
                    torch.cuda.ipc_collect()
        except Exception as e:
            print(f"内存清理警告: {e}")
    
    def _get_device(self, device: Optional[str]) -> str:
        """
        获取计算设备 - 增强版本
        智能检测并选择最佳可用设备
        
        Args:
            device: 指定设备
            
        Returns:
            设备名称
        """
        if device == 'auto' or device is None:
            # 多层次设备检测
            try:
                # 第一步：检查CUDA是否可用
                if torch.cuda.is_available():
                    # 第二步：检查CUDA是否真正可用（避免驱动问题）
                    try:
                        # 尝试创建一个简单的CUDA张量
                        test_tensor = torch.randn(2, 2, device='cuda')
                        _ = test_tensor + 1  # 简单运算测试
                        del test_tensor  # 立即释放测试张量
                        torch.cuda.empty_cache()  # 清空CUDA缓存
                        print("✅ 检测到CUDA支持且可正常使用，启用GPU加速")
                        return 'cuda'
                    except Exception as cuda_error:
                        print(f"⚠️ CUDA可用但运行异常，回退到CPU模式: {cuda_error}")
                        # 强制清理CUDA状态
                        try:
                            torch.cuda.empty_cache()
                        except:
                            pass
                        return 'cpu'
                else:
                    print("ℹ️ 未检测到CUDA支持，使用CPU模式")
                    return 'cpu'
            except Exception as e:
                print(f"⚠️ 设备检测失败，强制使用CPU模式: {e}")
                return 'cpu'
        
        # 验证指定设备的可用性
        if device == 'cuda':
            try:
                if torch.cuda.is_available():
                    # 测试CUDA设备
                    test_tensor = torch.randn(2, 2, device='cuda')
                    _ = test_tensor + 1
                    del test_tensor
                    torch.cuda.empty_cache()
                    print(f"✅ 指定CUDA设备验证成功")
                    return device
                else:
                    print("⚠️ 指定CUDA设备但CUDA不可用，回退到CPU")
                    return 'cpu'
            except Exception as e:
                print(f"⚠️ CUDA设备测试失败，回退到CPU: {e}")
                try:
                    torch.cuda.empty_cache()
                except:
                    pass
                return 'cpu'
        
        return device
    
    def load_model(self, cache_dir: Optional[str] = None) -> bool:
        """
        加载SegFormer模型
        
        Args:
            cache_dir: 模型缓存目录
            
        Returns:
            是否加载成功
        """
        try:
            print(f"正在加载模型: {self.model_name}")
            
            # 设置缓存目录
            if cache_dir is None:
                # 检查是否在打包环境中
                import sys
                if getattr(sys, 'frozen', False):
                    # 在PyInstaller打包的exe中运行
                    base_path = sys._MEIPASS
                    cache_dir = os.path.join(base_path, "models")
                else:
                    # 在开发环境中运行
                    cache_dir = os.path.join(os.getcwd(), "models")
            
            print(f"模型缓存目录: {cache_dir}")
            
            # 检查模型目录是否存在
            if not os.path.exists(cache_dir):
                print(f"模型目录不存在: {cache_dir}")
                # 尝试在当前目录查找
                cache_dir = os.path.join(os.getcwd(), "models")
                print(f"尝试使用备用目录: {cache_dir}")
            
            os.makedirs(cache_dir, exist_ok=True)
            
            # 加载处理器和模型
            print("正在加载图像处理器...")
            try:
                self.processor = SegformerImageProcessor.from_pretrained(
                    self.model_name, cache_dir=cache_dir, local_files_only=False
                )
                print("✅ 图像处理器加载成功")
            except Exception as e:
                print(f"❌ 图像处理器加载失败: {e}")
                raise
            
            print("正在加载语义分割模型...")
            try:
                # 首先尝试使用safetensors格式
                self.model = SegformerForSemanticSegmentation.from_pretrained(
                    self.model_name, cache_dir=cache_dir, local_files_only=False, use_safetensors=True
                )
                print("✅ 模型加载成功 (safetensors格式)")
            except Exception as e:
                print(f"⚠️ safetensors格式加载失败，尝试标准格式: {e}")
                try:
                    self.model = SegformerForSemanticSegmentation.from_pretrained(
                        self.model_name, cache_dir=cache_dir, local_files_only=False
                    )
                    print("✅ 模型加载成功 (标准格式)")
                except Exception as e2:
                    print(f"❌ 模型加载完全失败: {e2}")
                    raise
            
            # 移动模型到指定设备
            print(f"将模型移动到设备: {self.device}")
            try:
                self.model.to(self.device)
                self.model.eval()
                print(f"✅ 模型成功移动到 {self.device} 设备")
            except Exception as e:
                print(f"❌ 模型移动到设备失败: {e}")
                # 如果移动到指定设备失败，强制使用CPU
                if self.device != 'cpu':
                    print("尝试强制使用CPU模式...")
                    self.device = 'cpu'
                    self.model.to(self.device)
                    self.model.eval()
                    print("✅ 已切换到CPU模式")
                else:
                    raise
            
            self.model_loaded = True
            print("✅ 模型加载成功")
            return True
            
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            print(f"错误类型: {type(e).__name__}")
            import traceback
            print(f"详细错误信息: {traceback.format_exc()}")
            return False
    
    def _load_image_with_chinese_path(self, image_path: str) -> Image.Image:
        """
        加载图片，支持中文路径
        
        Args:
            image_path: 图片路径
            
        Returns:
            PIL图像对象
        """
        # 方法1：直接使用PIL打开
        try:
            image = Image.open(image_path).convert('RGB')
            return image
        except (OSError, UnicodeDecodeError, Exception):
            pass
        
        # 方法2：使用cv2读取后转换为PIL格式
        try:
            img_array = cv2.imread(image_path)
            if img_array is not None:
                # BGR转RGB
                img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(img_array)
                return image
        except Exception:
            pass
        
        # 方法3：使用numpy读取字节流
        try:
            with open(image_path, 'rb') as f:
                img_data = f.read()
            img_array = np.frombuffer(img_data, np.uint8)
            img_cv = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img_cv is not None:
                # BGR转RGB
                img_array = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(img_array)
                return image
        except Exception:
            pass
        
        raise ValueError(f"无法读取图片文件: {image_path}")
    
    def preprocess_image(self, image_path: str) -> Tuple[torch.Tensor, Image.Image]:
        """
        预处理图像
        
        Args:
            image_path: 图像路径
            
        Returns:
            处理后的张量和原始图像
        """
        # 加载图像 - 支持中文路径
        image = self._load_image_with_chinese_path(image_path)
        
        # 使用处理器预处理
        inputs = self.processor(images=image, return_tensors="pt")
        pixel_values = inputs['pixel_values'].to(self.device)
        
        # 立即清理inputs
        del inputs
        
        return pixel_values, image
    
    def segment_image(self, image_path: str) -> Tuple[np.ndarray, Image.Image]:
        """
        对图像进行语义分割
        
        Args:
            image_path: 图像路径
            
        Returns:
            分割结果和原始图像
        """
        if not self.model_loaded:
            raise RuntimeError("模型未加载，请先调用load_model()")
        
        try:
            # 预处理图像
            pixel_values, original_image = self.preprocess_image(image_path)
            
            # 进行推理
            with torch.no_grad():
                outputs = self.model(pixel_values=pixel_values)
                logits = outputs.logits
                
                # 立即清理pixel_values
                del pixel_values
                
                # 获取预测结果
                predictions = torch.nn.functional.interpolate(
                    logits,
                    size=original_image.size[::-1],  # (height, width)
                    mode="bilinear",
                    align_corners=False,
                )
                
                # 立即清理logits
                del logits
                
                # 转换为numpy数组
                predicted_segmentation_map = predictions.squeeze().cpu().numpy()
                del predictions  # 立即清理
                
                segmentation_map = np.argmax(predicted_segmentation_map, axis=0)
                del predicted_segmentation_map  # 立即清理
                
                # 清理outputs
                del outputs
            
            # 清理内存
            self._cleanup_memory()
            
            return segmentation_map, original_image
            
        except Exception as e:
            # 发生异常时也要清理内存
            self._cleanup_memory()
            raise e

    def analyze_image(self, image_path: str, output_dir: str, 
                     save_analysis: bool = True) -> Dict:
        """
        分析单张图像的绿视率
        
        Args:
            image_path: 图像路径
            output_dir: 输出目录
            save_analysis: 是否保存分析图像
            
        Returns:
            分析结果
        """
        if not self.model_loaded:
            raise RuntimeError("模型未加载，请先调用load_model()")
        
        try:
            # 只有在需要保存分析图像时才创建输出目录
            if save_analysis:
                os.makedirs(output_dir, exist_ok=True)
            
            # 进行语义分割
            segmentation_map, original_image = self.segment_image(image_path)
            
            # 计算绿视率
            analysis_result = self.calculate_green_view_rate(segmentation_map)
            
            # 生成文件名
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            
            # 保存分析图像 - 只保存合并的综合分析图片，不保存单独的掩膜图片
            analysis_paths = {}
            # 注释掉单独掩膜图片的保存，只通过 generate_comprehensive_analysis_image 生成合并图片
            # if save_analysis:
            #      # 创建植被掩码图
            #      vegetation_image = self.create_vegetation_mask(segmentation_map, original_image)
            #      vegetation_path = os.path.join(output_dir, f"{base_name}_vegetation.png")
            #      self._save_image_with_chinese_path(vegetation_image, vegetation_path)
            #      analysis_paths['vegetation_mask'] = vegetation_path
            #      
            #      # 立即清理植被图像
            #      del vegetation_image
            #      
            #      # 创建分割叠加图
            #      overlay_image = self.create_segmentation_overlay(segmentation_map, original_image)
            #      overlay_path = os.path.join(output_dir, f"{base_name}_overlay.png")
            #      self._save_image_with_chinese_path(overlay_image, overlay_path)
            #      analysis_paths['segmentation_overlay'] = overlay_path
            #      
            #      # 立即清理叠加图像
            #      del overlay_image
            #      
            #      # 中间内存清理
            #      gc.collect()
            
            # 添加路径信息到结果，包含segmentation_map用于生成综合分析图片
            analysis_result.update({
                'image_path': image_path,
                'original_image_path': image_path,
                'analysis_paths': analysis_paths,
                'segmentation_map': segmentation_map  # 保留用于生成综合分析图片
            })
            
            # 清理原始图像对象（保留segmentation_map）
            del original_image
            
            # 最终内存清理
            self._cleanup_memory()
            
            return analysis_result
            
        except Exception as e:
            # 发生异常时也要清理内存
            self._cleanup_memory()
            raise e

    def analyze_batch(self, image_paths: List[str], output_dir: str, 
                     progress_callback=None, save_analysis: bool = True) -> List[Dict]:
        """
        批量分析图像绿视率
        
        Args:
            image_paths: 图像路径列表
            output_dir: 输出目录
            progress_callback: 进度回调函数
            
        Returns:
            分析结果列表
        """
        results = []
        total = len(image_paths)
        
        for i, image_path in enumerate(image_paths):
            try:
                result = self.analyze_image(image_path, output_dir, save_analysis)
                results.append(result)
                
                if progress_callback:
                    progress_callback(i + 1, total, result)
                    
                # 每处理一张图片后清理内存
                self._cleanup_memory()
                
                # 每处理5张图片进行一次深度清理
                if (i + 1) % 5 == 0:
                    # 额外的深度清理
                    for _ in range(5):
                        gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                    
            except Exception as e:
                error_result = {
                    'original_image_path': image_path,
                    'error': str(e),
                    'green_view_rate': 0.0
                }
                results.append(error_result)
                
                if progress_callback:
                    progress_callback(i + 1, total, error_result)
                    
                print(f"分析图像失败 {image_path}: {e}")
        
        return results

    def calculate_green_view_rate(self, segmentation_map: np.ndarray) -> Dict:
        """
        计算绿视率
        
        Args:
            segmentation_map: 分割结果图
            
        Returns:
            绿视率分析结果
        """
        # 统计像素数量
        total_pixels = segmentation_map.size
        vegetation_pixels = np.sum(segmentation_map == self.VEGETATION_CLASS_ID)
        
        # 计算绿视率
        green_view_rate = (vegetation_pixels / total_pixels) * 100
        
        # 统计各类别像素数量
        class_counts = {}
        for class_id in range(len(self.CITYSCAPES_CLASSES)):
            count = np.sum(segmentation_map == class_id)
            if count > 0:
                class_name = self.CITYSCAPES_CLASSES.get(class_id, f'class_{class_id}')
                class_counts[class_name] = {
                    'pixels': int(count),
                    'percentage': (count / total_pixels) * 100
                }
        
        return {
            'green_view_rate': green_view_rate,
            'vegetation_pixels': int(vegetation_pixels),
            'total_pixels': int(total_pixels),
            'class_distribution': class_counts
        }
    
    def create_vegetation_mask(self, segmentation_map: np.ndarray, 
                             original_image: Image.Image) -> Image.Image:
        """
        创建植被高亮图像
        
        Args:
            segmentation_map: 分割结果图
            original_image: 原始图像
            
        Returns:
            植被高亮图像
        """
        # 转换原始图像为numpy数组
        img_array = np.array(original_image)
        
        # 创建植被掩码
        vegetation_mask = segmentation_map == self.VEGETATION_CLASS_ID
        
        # 创建高亮图像
        highlight_image = img_array.copy()
        
        # 将植被区域高亮为绿色
        highlight_image[vegetation_mask] = [0, 255, 0]  # 绿色
        
        # 将非植被区域调暗
        non_vegetation_mask = ~vegetation_mask
        highlight_image[non_vegetation_mask] = (highlight_image[non_vegetation_mask] * 0.6).astype(np.uint8)
        
        return Image.fromarray(highlight_image)
    
    def create_segmentation_overlay(self, segmentation_map: np.ndarray, 
                                  original_image: Image.Image, alpha: float = 0.6) -> Image.Image:
        """
        创建分割结果叠加图像
        
        Args:
            segmentation_map: 分割结果图
            original_image: 原始图像
            alpha: 透明度
            
        Returns:
            叠加图像
        """
        # 创建彩色分割图
        color_map = self._create_color_map()
        colored_segmentation = np.zeros((*segmentation_map.shape, 3), dtype=np.uint8)
        
        for class_id, color in color_map.items():
            mask = segmentation_map == class_id
            colored_segmentation[mask] = color
        
        # 转换为PIL图像
        segmentation_image = Image.fromarray(colored_segmentation)
        
        # 调整大小匹配原始图像
        segmentation_image = segmentation_image.resize(original_image.size)
        
        # 叠加图像
        overlay = Image.blend(original_image, segmentation_image, alpha)
        
        return overlay
    
    def _create_color_map(self) -> Dict[int, Tuple[int, int, int]]:
        """
        创建类别颜色映射
        
        Returns:
            颜色映射字典
        """
        colors = [
            (128, 64, 128),   # road
            (244, 35, 232),   # sidewalk
            (70, 70, 70),     # building
            (102, 102, 156),  # wall
            (190, 153, 153),  # fence
            (153, 153, 153),  # pole
            (250, 170, 30),   # traffic light
            (220, 220, 0),    # traffic sign
            (107, 142, 35),   # vegetation
            (152, 251, 152),  # terrain
            (70, 130, 180),   # sky
            (220, 20, 60),    # person
            (255, 0, 0),      # rider
            (0, 0, 142),      # car
            (0, 0, 70),       # truck
            (0, 60, 100),     # bus
            (0, 80, 100),     # train
            (0, 0, 230),      # motorcycle
            (119, 11, 32),    # bicycle
        ]
        
        return {i: colors[i] if i < len(colors) else (128, 128, 128) 
                for i in range(len(self.CITYSCAPES_CLASSES))}
    
    def _save_image_with_chinese_path(self, image: Image.Image, file_path: str):
        """
        保存图片，支持中文路径
        
        Args:
            image: PIL图像对象
            file_path: 保存路径
        """
        try:
            # 方法1：直接保存
            image.save(file_path)
        except (OSError, UnicodeEncodeError):
            # 方法2：使用cv2保存（支持中文路径）
            # 先保存到临时文件
            temp_path = tempfile.mktemp(suffix='.jpg')
            image.save(temp_path)
            # 再移动到目标路径
            shutil.move(temp_path, file_path)

# 测试函数
def test_analyzer():
    """测试图像处理模块"""
    analyzer = GreenViewAnalyzer()
    
    # 加载模型
    if analyzer.load_model():
        print("模型加载成功")
        
        # 测试图像分析（需要有测试图像）
        # result = analyzer.analyze_image("test_image.jpg", "./output")
    else:
        print("模型加载失败")

if __name__ == "__main__":
    test_analyzer()