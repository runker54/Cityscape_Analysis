#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
坐标自动获取模块
使用百度地图API批量获取指定区域和类型的经纬度坐标
"""

import requests
import json
import time
import logging
from typing import List, Dict, Optional, Tuple
import pandas as pd
from urllib.parse import quote

class CoordinateCollector:
    """坐标收集器 - 使用百度地图API获取POI坐标"""
    
    def __init__(self, ak: str = None):
        """
        初始化坐标收集器
        
        Args:
            ak: 百度地图API密钥
        """
        self.ak = ak
        self.base_url = "https://api.map.baidu.com/place/v2/search"
        self.geocoding_url = "https://api.map.baidu.com/geocoding/v3"
        self.logger = logging.getLogger(__name__)
        
        # 预定义的POI类型映射
        self.poi_types = {
            "学校": "教育培训",
            "医院": "医疗保健",
            "政府单位": "政府机构",
            "公园": "旅游景点",
            "商场": "购物",
            "银行": "金融保险",
            "酒店": "酒店",
            "餐厅": "美食",
            "加油站": "汽车服务",
            "地铁站": "交通设施"
        }
        
        # 省份和城市代码映射（部分示例）
        self.region_codes = {
            "北京市": "131",
            "上海市": "289",
            "广州市": "257",
            "深圳市": "340",
            "杭州市": "179",
            "南京市": "315",
            "武汉市": "218",
            "成都市": "75",
            "西安市": "233"
        }
    
    def set_api_key(self, ak: str):
        """设置百度地图API密钥"""
        self.ak = ak
    
    def get_city_coordinates(self, city_name: str) -> Optional[Tuple[float, float]]:
        """
        获取城市中心坐标
        
        Args:
            city_name: 城市名称
            
        Returns:
            (纬度, 经度) 或 None
        """
        if not self.ak:
            self.logger.error("请先设置百度地图API密钥")
            return None
            
        try:
            params = {
                'address': city_name,
                'output': 'json',
                'ak': self.ak
            }
            
            response = requests.get(self.geocoding_url, params=params, timeout=10)
            data = response.json()
            
            if data['status'] == 0 and data['result']:
                location = data['result']['location']
                return location['lat'], location['lng']
            else:
                self.logger.error(f"获取城市坐标失败: {data.get('message', '未知错误')}")
                return None
                
        except Exception as e:
            self.logger.error(f"获取城市坐标异常: {e}")
            return None
    
    def search_pois(self, query: str, region: str, poi_type: str = None, 
                   page_size: int = 20, max_pages: int = 10) -> List[Dict]:
        """
        搜索POI点
        
        Args:
            query: 搜索关键词
            region: 搜索区域（城市名）
            poi_type: POI类型
            page_size: 每页结果数量
            max_pages: 最大页数
            
        Returns:
            POI列表
        """
        if not self.ak:
            self.logger.error("请先设置百度地图API密钥")
            return []
        
        all_pois = []
        
        try:
            for page in range(max_pages):
                params = {
                    'query': query,
                    'region': region,
                    'output': 'json',
                    'ak': self.ak,
                    'page_size': page_size,
                    'page_num': page,
                    'scope': '2'  # 返回详细信息
                }
                
                if poi_type and poi_type in self.poi_types:
                    params['tag'] = self.poi_types[poi_type]
                
                response = requests.get(self.base_url, params=params, timeout=10)
                data = response.json()
                
                if data['status'] == 0 and 'results' in data:
                    results = data['results']
                    if not results:
                        break
                        
                    for poi in results:
                        poi_info = {
                            'name': poi.get('name', ''),
                            'address': poi.get('address', ''),
                            'latitude': poi['location']['lat'],
                            'longitude': poi['location']['lng'],
                            'type': poi.get('detail_info', {}).get('tag', ''),
                            'area': poi.get('area', ''),
                            'city': region,
                            'telephone': poi.get('telephone', ''),
                            'uid': poi.get('uid', '')
                        }
                        all_pois.append(poi_info)
                    
                    # 如果返回结果少于页面大小，说明已经是最后一页
                    if len(results) < page_size:
                        break
                        
                else:
                    self.logger.error(f"搜索POI失败: {data.get('message', '未知错误')}")
                    break
                
                # 添加延时避免请求过快
                time.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"搜索POI异常: {e}")
        
        self.logger.info(f"在{region}搜索到{len(all_pois)}个{query}相关POI")
        return all_pois
    
    def batch_collect_coordinates(self, regions: List[str], poi_types: List[str], 
                                keywords: List[str] = None) -> pd.DataFrame:
        """
        批量收集坐标
        
        Args:
            regions: 区域列表（城市名）
            poi_types: POI类型列表
            keywords: 额外关键词列表
            
        Returns:
            包含所有坐标的DataFrame
        """
        all_coordinates = []
        
        for region in regions:
            self.logger.info(f"正在处理区域: {region}")
            
            for poi_type in poi_types:
                self.logger.info(f"正在搜索类型: {poi_type}")
                
                # 使用POI类型作为关键词搜索
                pois = self.search_pois(poi_type, region, poi_type)
                all_coordinates.extend(pois)
                
                # 如果有额外关键词，组合搜索
                if keywords:
                    for keyword in keywords:
                        combined_query = f"{poi_type} {keyword}"
                        pois = self.search_pois(combined_query, region, poi_type)
                        all_coordinates.extend(pois)
                
                time.sleep(0.2)  # 避免请求过快
        
        # 去重处理
        df = pd.DataFrame(all_coordinates)
        if not df.empty:
            # 基于坐标去重（允许小的坐标差异）
            df = df.drop_duplicates(subset=['name', 'address'], keep='first')
            df = df.reset_index(drop=True)
        
        self.logger.info(f"总共收集到{len(df)}个有效坐标点")
        return df
    
    def save_coordinates(self, df: pd.DataFrame, output_path: str, 
                        format_type: str = 'excel') -> bool:
        """
        保存坐标数据
        
        Args:
            df: 坐标数据DataFrame
            output_path: 输出路径
            format_type: 格式类型 ('excel', 'csv', 'json')
            
        Returns:
            是否保存成功
        """
        try:
            if format_type.lower() == 'excel':
                df.to_excel(output_path, index=False, engine='openpyxl')
            elif format_type.lower() == 'csv':
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
            elif format_type.lower() == 'json':
                df.to_json(output_path, orient='records', ensure_ascii=False, indent=2)
            else:
                raise ValueError(f"不支持的格式类型: {format_type}")
            
            self.logger.info(f"坐标数据已保存到: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存坐标数据失败: {e}")
            return False
    
    def get_available_poi_types(self) -> List[str]:
        """获取可用的POI类型列表"""
        return list(self.poi_types.keys())
    
    def validate_api_key(self) -> bool:
        """
        验证API密钥是否有效
        
        Returns:
            API密钥是否有效
        """
        if not self.ak:
            return False
            
        try:
            # 使用一个简单的地理编码请求来验证API密钥
            params = {
                'address': '北京市',
                'output': 'json',
                'ak': self.ak
            }
            
            response = requests.get(self.geocoding_url, params=params, timeout=5)
            data = response.json()
            
            return data['status'] == 0
            
        except Exception as e:
            self.logger.error(f"验证API密钥异常: {e}")
            return False


def main():
    """测试函数"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建收集器实例
    collector = CoordinateCollector()
    
    # 注意：需要设置有效的百度地图API密钥
    # collector.set_api_key("your_baidu_api_key_here")
    
    print("可用的POI类型:")
    for poi_type in collector.get_available_poi_types():
        print(f"- {poi_type}")
    
    # 示例：批量收集坐标
    # regions = ["北京市", "上海市"]
    # poi_types = ["学校", "医院"]
    # df = collector.batch_collect_coordinates(regions, poi_types)
    # collector.save_coordinates(df, "coordinates.xlsx")


if __name__ == "__main__":
    main()