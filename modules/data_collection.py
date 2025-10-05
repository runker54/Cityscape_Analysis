#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据采集模块 - 百度全景静态图API调用和图片下载

功能：
1. 解析用户输入的经纬度坐标
2. 调用百度全景静态图API下载图片
3. 保存图片到指定目录
4. 记录下载信息

注意：使用百度全景静态图API，只需要ak参数，不需要sk参数
API文档：https://lbsyun.baidu.com/index.php?title=viewstatic
"""

import os
import requests
import pandas as pd
from typing import List, Tuple, Dict, Optional
from urllib.parse import urlencode
import time
from tqdm import tqdm

class BaiduStreetViewCollector:
    """百度街景图片采集器"""
    
    def __init__(self, ak: str, sk: Optional[str] = None):
        """
        初始化采集器
        
        Args:
            ak: 百度地图API的Access Key
            sk: 百度地图API的Secret Key (已弃用，全景静态图API不需要sk)
        """
        self.ak = ak
        self.sk = sk  # 保留兼容性，但全景静态图API不使用
        self.api_url = "https://api.map.baidu.com/panorama/v2"
        self.download_records = []
        
    def parse_coordinates(self, coord_text: str) -> List[Tuple[float, float]]:
        """
        解析坐标文本，支持多种格式
        
        Args:
            coord_text: 坐标文本，支持多行输入
            
        Returns:
            坐标列表 [(lng, lat), ...]
        """
        coordinates = []
        lines = coord_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 尝试解析经纬度
            try:
                # 支持逗号分隔
                if ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        lng = float(parts[0].strip())
                        lat = float(parts[1].strip())
                        coordinates.append((lng, lat))
                # 支持空格分隔
                elif ' ' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        lng = float(parts[0])
                        lat = float(parts[1])
                        coordinates.append((lng, lat))
            except ValueError:
                print(f"警告: 无法解析坐标行: {line}")
                continue
                
        return coordinates
    
    def parse_excel_coordinates(self, excel_path: str, lng_col: str = 'lon', lat_col: str = 'lat') -> List[Tuple[float, float]]:
        """
        从Excel文件中解析坐标
        
        Args:
            excel_path: Excel文件路径
            lng_col: 经度列名
            lat_col: 纬度列名
            
        Returns:
            坐标列表 [(lng, lat), ...]
        """
        try:
            df = pd.read_excel(excel_path)
            coordinates = []
            
            for _, row in df.iterrows():
                try:
                    lng = float(row[lng_col])
                    lat = float(row[lat_col])
                    coordinates.append((lng, lat))
                except (ValueError, KeyError) as e:
                    print(f"警告: 无法解析Excel行数据: {e}")
                    continue
                    
            return coordinates
        except Exception as e:
            print(f"错误: 无法读取Excel文件: {e}")
            return []
    
    def build_api_url(self, lng: float, lat: float, width: int = 1024, height: int = 512, 
                     fov: int = 180, coordtype: str = 'wgs84ll') -> str:
        """
        构建百度全景静态图API请求URL
        
        Args:
            lng: 经度
            lat: 纬度
            width: 图片宽度 (范围[10,4096])
            height: 图片高度 (范围[10,512])
            fov: 水平视野角度 (默认180度，范围[10,360])
            coordtype: 坐标类型 (wgs84ll-GPS坐标, bd09ll-百度坐标, gcj02-谷歌高德坐标)
            
        Returns:
            API请求URL
        """
        params = {
            'ak': self.ak,
            'location': f'{lng},{lat}',
            'width': width,
            'height': height,
            'fov': fov,
            'coordtype': coordtype
        }
        
        return f"{self.api_url}?{urlencode(params)}"
    
    def download_image(self, lng: float, lat: float, save_dir: str, 
                      filename: Optional[str] = None, **kwargs) -> Dict:
        """
        下载单张街景图片
        
        Args:
            lng: 经度
            lat: 纬度
            save_dir: 保存目录
            filename: 文件名（可选）
            **kwargs: 其他API参数
            
        Returns:
            下载结果字典
        """
        # 确保保存目录存在
        os.makedirs(save_dir, exist_ok=True)
        
        # 生成文件名
        if filename is None:
            filename = f"streetview_{lng}_{lat}.jpg"
        
        filepath = os.path.join(save_dir, filename)
        
        # 构建API URL
        api_url = self.build_api_url(lng, lat, **kwargs)
        
        try:
            # 发送请求
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            
            # 检查响应内容类型
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type:
                return {
                    'success': False,
                    'lng': lng,
                    'lat': lat,
                    'filepath': None,
                    'error': f'响应不是图片格式: {content_type}'
                }
            
            # 保存图片
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            # 记录下载信息
            record = {
                'success': True,
                'lng': lng,
                'lat': lat,
                'filepath': filepath,
                'filename': filename,
                'file_size': len(response.content),
                'download_time': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.download_records.append(record)
            return record
            
        except requests.exceptions.RequestException as e:
            error_record = {
                'success': False,
                'lng': lng,
                'lat': lat,
                'filepath': None,
                'error': str(e)
            }
            self.download_records.append(error_record)
            return error_record
    
    def download_batch(self, coordinates: List[Tuple[float, float]], save_dir: str, 
                      progress_callback=None, **kwargs) -> List[Dict]:
        """
        批量下载街景图片
        
        Args:
            coordinates: 坐标列表
            save_dir: 保存目录
            progress_callback: 进度回调函数
            **kwargs: 其他API参数
            
        Returns:
            下载结果列表
        """
        results = []
        total = len(coordinates)
        
        # 使用tqdm显示进度条
        with tqdm(total=total, desc="下载街景图片") as pbar:
            for i, (lng, lat) in enumerate(coordinates):
                result = self.download_image(lng, lat, save_dir, **kwargs)
                results.append(result)
                
                # 更新进度
                pbar.update(1)
                if progress_callback:
                    progress_callback(i + 1, total, result)
                
                # 添加延时避免API限制
                time.sleep(0.1)
        
        return results
    
    def get_download_summary(self) -> Dict:
        """
        获取下载统计信息
        
        Returns:
            统计信息字典
        """
        total = len(self.download_records)
        success = sum(1 for r in self.download_records if r['success'])
        failed = total - success
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'success_rate': success / total * 100 if total > 0 else 0
        }
    
    def save_download_log(self, log_path: str):
        """
        保存下载日志到Excel文件
        
        Args:
            log_path: 日志文件路径
        """
        if not self.download_records:
            print("没有下载记录可保存")
            return
        
        df = pd.DataFrame(self.download_records)
        df.to_excel(log_path, index=False)
        print(f"下载日志已保存到: {log_path}")
    
    def clear_records(self):
        """清空下载记录"""
        self.download_records.clear()

# 测试函数
def test_collector():
    """测试数据采集模块"""
    # 注意：需要有效的百度地图API密钥（ak），全景静态图API不需要sk
    ak = "your_baidu_ak_here"
    collector = BaiduStreetViewCollector(ak)
    
    # 测试坐标解析
    coord_text = "116.404, 39.915\n121.473, 31.230"
    coordinates = collector.parse_coordinates(coord_text)
    print(f"解析到坐标: {coordinates}")
    
    # 测试单张图片下载（需要有效的API密钥）
    # result = collector.download_image(116.404, 39.915, "./test_images")
    # print(f"下载结果: {result}")

if __name__ == "__main__":
    test_collector()