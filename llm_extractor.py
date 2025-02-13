"""LLM关键词提取模块

整体处理逻辑:
1. 支持多种LLM服务(Deepseek/Ollama)的API调用
2. 根据输入文本构建提示词(Prompt)
3. 发送API请求获取关键词列表
4. 验证并标准化API返回的结果格式
5. 为每个关键词分配权重值(0-1)

支持的LLM服务:
- Deepseek Chat: 基于Deepseek商业API
- Ollama: 基于本地Ollama开源模型

依赖项:
- requests: API请求
- json: 结果解析
"""

from typing import Dict, List, Any, Optional
import json
import requests
from config import API_CONFIG
from utils import logger

class BaseLLMExtractor:
    """LLM提取器基类"""
    
    def extract_keywords(self, text: str) -> List[Dict[str, Any]]:
        """提取关键词的抽象方法"""
        raise NotImplementedError
        
    def _validate_keywords(self, keywords: List[Dict[str, Any]]) -> bool:
        """验证LLM返回的关键词列表是否符合预期格式
        
        验证规则:
        1. 检查输入是否为列表类型
        2. 检查每个元素是否为字典类型
        3. 验证字典是否包含必需的key
           - keyword: 关键词文本
           - weight: 权重值
        4. 验证关键词是否为字符串类型
        5. 验证权重是否为数值类型且在0-1之间
        
        Args:
            keywords: List[Dict[str, Any]], 待验证的关键词列表
            
        Returns:
            bool: 验证结果
                - True: 完全符合格式要求
                - False: 存在任何格式错误
                
        示例:
            有效的关键词列表格式:
            [
                {"keyword": "经济发展", "weight": 0.95},
                {"keyword": "科技创新", "weight": 0.88}  
            ]
        """
        if not isinstance(keywords, list):
            return False
            
        for item in keywords:
            if not isinstance(item, dict):
                return False
            if 'keyword' not in item or 'weight' not in item:
                return False
            if not isinstance(item['keyword'], str):
                return False
            if not isinstance(item['weight'], (int, float)):
                return False
            if not 0 <= item['weight'] <= 1:
                return False
        return True

    def _extract_json_array(self, text: str) -> str:
        """从LLM响应文本中提取JSON数组字符串
        
        处理逻辑:
        1. 查找文本中第一个左方括号'['的位置
        2. 查找最后一个右方括号']'的位置
        3. 提取这两个位置之间的内容
        
        Args:
            text: str, LLM返回的完整响应文本
            
        Returns:
            str: JSON数组字符串。如果没找到有效的JSON数组,返回原始文本
            
        注意:
            该方法假设文本中只包含一个有效的JSON数组。如果文本中
            包含多个JSON数组,只会返回第一个完整的数组。
        """
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1:
            return text[start:end + 1]
        return text

class DeepseekExtractor(BaseLLMExtractor):
    """基于Deepseek的关键词提取器"""
    
    def extract_keywords(self, text: str) -> List[Dict[str, Any]]:
        """使用Deepseek API提取关键词
        
        Args:
            text: 输入文本
            
        Returns:
            List[Dict[str, Any]]: 关键词列表
        """
        try:
            headers = {
                'Authorization': f"Bearer {API_CONFIG['DEEPSEEK_API_KEY']}",
                'Content-Type': 'application/json'
            }

            prompt = self._build_prompt(text)
            response = requests.post(
                f"{API_CONFIG['DEEPSEEK_API_BASE']}/chat/completions",
                headers=headers,
                json=self._build_request_body(prompt),
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()['choices'][0]['message']['content']
                json_content = self._extract_json_array(result)
                keywords = json.loads(json_content)
                
                if self._validate_keywords(keywords):
                    return keywords
                    
            logger.error(f"Deepseek API error: {response.text}")
            return []

        except requests.exceptions.Timeout:
            logger.error("Deepseek API timeout")
            return []
        except Exception as e:
            logger.error(f"Error extracting keywords with Deepseek: {str(e)}")
            return []
            
    def _build_prompt(self, text: str) -> str:
        """构建用于LLM API的提示词模板
        
        处理逻辑:
        1. 使用预定义的提示词模板,优化API的输出质量
        2. 指定关键词提取的任务要求,包括需要的数量(10-15)
        3. 给出严格的JSON格式限制,确保结果一致性
        4. 添加权重赋值要求(0-1区间)
        5. 附加完整的示例说明,增强提示词可理解性
        
        提示词组成:
        1. 任务目标:提取10-15个关键词并赋权重
        2. 格式要求:JSON Array格式,并给出示例结构
        3. 数值规范:权重值限定在0-1之间
        4. 示例结果:包含正确的格式和典型内容
        5. 输入内容:待分析的文本数据
        
        Args:
            text: str, 待分析的具体文本内容
            
        Returns:
            str: 完整的提示词字符串,可直接用于API调用
            
        示例:
            输入文本: "人工智能技术飞速发展..."
            
            生成的提示词:
            ```
            请根据以下文本,提取10-15个最重要的核心关键词...
            [
                {"keyword": "关键词1", "weight": 0.9},
                {"keyword": "关键词2", "weight": 0.85}
            ]
            文本内容:
            人工智能技术飞速发展...
            ```
        """
        return f"""请根据以下文本,提取10-15个最重要的核心关键词并给出重要性权重(0-1之间)。
            请严格按照下面的JSON数组格式返回结果:
            [
                {{"keyword": "关键词1", "weight": 0.9}},
                {{"keyword": "关键词2", "weight": 0.85}}
            ]

            文本内容:
            {text}
            """
            
    def _build_request_body(self, prompt: str) -> Dict:
        """构建用于API调用的请求体参数
        
        处理逻辑:
        1. 构造标准化的API调用参数字典
        2. 设置关键配置项:
           - 指定使用的模型名称(deepseek-chat)
           - 构建对话上下文消息列表
           - 配置生成参数(temperature等)
        3. 确保所有参数符合API文档规范
        
        消息列表结构:
        1. system: 设置助手角色为关键词提取专家
        2. user: 包含完整的提示词内容
        
        参数配置:
        1. model: 使用的语言模型标识符
        2. messages: 包含角色和内容的消息数组
        3. temperature: 控制输出随机性的温度值
            - 0.3: 低温设定,保证输出稳定性
            - 仍保留适度变化空间
            
        Args:
            prompt: str, 经过格式化的完整提示词
            
        Returns:
            Dict: 符合API要求的请求体字典:
                - model: str, 模型标识符
                - messages: List[Dict], 对话消息列表
                - temperature: float, 生成参数
                
        示例:
            >>> prompt = "分析以下文本..."
            >>> body = self._build_request_body(prompt)
            >>> body
            {
                'model': 'deepseek-chat',
                'messages': [
                    {'role': 'system', 'content': '...'},
                    {'role': 'user', 'content': '...'}
                ],
                'temperature': 0.3
            }
        """
        return {
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'system', 'content': '你是一个关键词提取专家'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.3
        }

class OllamaExtractor(BaseLLMExtractor):
    """基于Ollama的关键词提取器"""
    
    MAX_RETRIES = 5
    
    def extract_keywords(self, text: str) -> List[Dict[str, Any]]:
        """使用Ollama API提取关键词
        
        Args:
            text: 输入文本
            
        Returns:
            List[Dict[str, Any]]: 关键词列表
        """
        messages = [
            {
                'role': 'system',
                'content': '你是一个专业的关键词提取助手。你必须始终以严格的JSON数组格式返回结果。'
            },
            {
                'role': 'user',
                'content': self._build_initial_prompt(text)
            }
        ]

        try:
            headers = {'Content-Type': 'application/json'}

            for attempt in range(self.MAX_RETRIES):
                response = requests.post(
                    f"{API_CONFIG['OLLAMA_API_BASE']}/api/chat",
                    headers=headers,
                    json=self._build_request_body(messages),
                    timeout=60
                )

                if response.status_code != 200:
                    logger.error(f"Ollama API error: {response.text}")
                    continue

                result = response.json()['message']['content']
                json_content = self._extract_json_array(result)

                try:
                    keywords = json.loads(json_content)
                    if self._validate_keywords(keywords):
                        return keywords
                except json.JSONDecodeError:
                    pass

                if attempt < self.MAX_RETRIES - 1:
                    messages.extend([
                        {'role': 'assistant', 'content': result},
                        {'role': 'user', 'content': self._build_correction_prompt()}
                    ])
                    logger.info(f"Retry {attempt + 1}: Invalid format, attempting correction")

            logger.error("Maximum retries reached, failed to get valid response")
            return []

        except requests.exceptions.Timeout:
            logger.error("Ollama API timeout")
            return []
        except Exception as e:
            logger.error(f"Error extracting keywords with Ollama: {str(e)}")
            return []
            
    def _build_initial_prompt(self, text: str) -> str:
        """构建初始提示词"""
        return f"""请分析下面的文本，完成以下任务：
            1. 提取10-15个最重要的核心关键词
            2. 给每个关键词分配0-1之间的重要性权重
            3. 必须严格按照以下JSON格式返回结果：
            [
                {{"keyword": "经济发展", "weight": 0.95}},
                {{"keyword": "科技创新", "weight": 0.88}}
            ]
            
            文本内容:
            {text}
            """
            
    def _build_correction_prompt(self) -> str:
        """构建纠正提示词"""
        return """你的上一次回复格式不正确。请严格按照以下JSON格式返回结果：
            [
                {"keyword": "关键词1", "weight": 权重值},
                {"keyword": "关键词2", "weight": 权重值}
            ]
            """
            
    def _build_request_body(self, messages: List[Dict]) -> Dict:
        """构建请求体"""
        return {
            'model': API_CONFIG['OLLAMA_MODEL'],
            'messages': messages,
            'stream': False
        }