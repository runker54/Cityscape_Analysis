1. TRAE 开发文档：百度街景图片绿视率分析工具
1.1 项目概览
本项目旨在开发一款桌面应用程序，用于自动化处理城市绿视率分析。该程序的核心功能包括：
1. 用户输入：接收用户提供的百度街景API密钥和感兴趣的研究区域。
2. 数据采集：通过调用百度街景API，下载指定区域的街景图片。
3. 图像处理：使用预训练的 NVIDIA SegFormer (nvidia/segformer-b5-finetuned-cityscapes-1024-1024) 模型对下载的图片进行语义分割，提取植被区域。
4. 数据分析：计算每张图片中植被像素所占的比例，即绿视率。
5. 结果输出：
• 将分割后的分析图片保存到指定目录。
• 生成包含每张图片详细信息的 Excel 报表，包括经纬度、原始图片路径、分析结果图片路径和计算得到的绿视率。
1.2 技术栈
• 编程语言：Python
• GUI框架：PyQt5
• 图像处理库：Pillow 或 OpenCV
• 深度学习框架：PyTorch 或 TensorFlow
• 模型：Nytia SegFormer (来自 Hugging Face transformers 库)
• 数据处理：pandas
• API调用：requests
• 文件操作：os, shutil
• 打包：PyInstaller (生成 .exe 可执行文件)
￼
2. 功能模块与实现细节
2.1 界面设计 (PyQt5)
主窗口
• API密钥输入框：用于输入百度的 AK (Access Key) 和 SK (Secret Key)。
• 研究区域输入：用户可以输入单个经纬度坐标，或者输入多个坐标，每个坐标占一行，或者直接导入excel表格，并指定lon和lat列。所有坐标模型使用wgs84坐标系，具体细节参考"https://lbsyun.baidu.com/index.php?title=viewstatic"。
• 保存路径选择：一个按钮，用于打开文件对话框，让用户选择保存下载图片和结果的文件夹。
• 功能按钮：
• “开始下载”：点击后触发街景图片下载功能。
• “开始分析”：点击后触发图像分割和绿视率计算功能。
• “导出报表”：点击后将结果导出为 Excel 文件。
• 状态栏/日志显示区：显示当前任务进度，例如“正在下载第 10/100 张图片”、“正在处理第 5/50 张图片”等信息。
2.2 数据采集模块 (百度街景 API)
• API端点：http://api.map.baidu.com/panorama/v2
• 参数：
• ak：用户的 Access Key。
• location：经纬度坐标，格式为 lng,lat。
• width & height：图片尺寸。
• fov：水平视野，影响图片内容。
• pitch：俯仰角。
• 实现步骤：
1. 从用户输入的文本中解析出所有经纬度坐标。
2. 循环遍历每个坐标，构造 API 请求 URL。
3. 使用 requests 库发送 GET 请求。
4. 如果请求成功，将返回的图片数据保存到用户指定的文件夹中。
5. 记录每张图片的经纬度信息和保存路径。
2.3 图像处理与分析模块 (SegFormer)
• 模型准备：
• 使用 Hugging Face transformers 库加载 nvidia/segformer-b5-finetuned-cityscapes-1024-1024 模型，并下载到当前目录下，最好导出为方便打包为后续和整体脚本打包为exe的格式。
• 这个模型是针对城市景观训练的，能够识别包括植被在内的多种地物，用户电脑如果有显卡便支持显卡。没有就使用cpu。
• 分割植被：
1. 加载下载的每一张街景图片。
2. 将图片输入到 SegFormer 模型中进行语义分割。
3. 模型会输出一个包含每个像素类别预测结果的张量。
4. 查找代表植被 (Vegetation) 类别的像素索引。Cityscapes 数据集中的植被类别 ID 通常是 18。请在实际使用前再次确认。
• 计算绿视率：
1. 统计分割结果中，植被类别像素的总数。
2. 统计图片的总像素数 (width * height)。
3. 绿视率 = (植被像素数 / 总像素数) * 100%。
• 保存分析图片：
1. 创建一个新的空白图片。
2. 将分割结果中属于植被的像素用绿色或其他醒目颜色填充。
3. 将这张“植被高亮”的图片保存到指定目录。
2.4 结果导出模块 (Excel)
• 数据结构：
• 使用 pandas.DataFrame 来组织数据。
• 列名可以包括：经度 (Longitude)、纬度 (Latitude)、原始图片路径 (Original Image Path)、分析图片路径 (Analysis Image Path)、绿视率 (Green View Index)。
• 实现步骤：
1. 创建一个空的 pandas.DataFrame。
2. 遍历每张已处理的图片，并将相关信息（经纬度、路径、绿视率）添加到 DataFrame 中。
3. 使用 DataFrame.to_excel() 方法将数据保存为 .xlsx 格式的 Excel 文件。