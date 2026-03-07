from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp
import os
import tempfile
import base64
import requests
import json

def save_base64_to_temp(logo_data):
    # 提取 Base64 数据
    if logo_data.startswith('data:image'):
        # 分离 MIME 类型和 Base64 数据
        header, base64_data = logo_data.split(',', 1)
        # 提取图片扩展名
        extension = header.split(';')[0].split('/')[1]
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=f'.{extension}', delete=False) as temp_file:
            # 解码 Base64 并写入文件
            temp_file.write(base64.b64decode(base64_data))
            temp_file_path = temp_file.name
        
        return temp_file_path
    return None


@register("list", "MC_Stomato", "一个简单的服务器查询插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.user_configs = {}

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    @filter.command("list")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 list 指令"""
        session_id = event.get_session_id()
        
        if session_id not in self.user_configs:
            yield event.plain_result("请先获取ip端口")
            return
        
        ip = self.user_configs[session_id]["ip"]
        port = self.user_configs[session_id]["port"]
        api_url = f"https://www.minecraftservers.cn/api/query?ip={ip}%3A{port}"
        response = requests.get(api_url)
        api = response.json()

        # 处理 logo 图片
        logo_data = api['data']['logo']
        if logo_data:
            # 保存 Base64 到临时文件
            temp_file_path = save_base64_to_temp(logo_data)

        chain = [
            Comp.Image.fromFileSystem(temp_file_path),
            Comp.Plain(f"motd:{api['data']['motd']}\n"),
            Comp.Plain(f"玩家人数:{api['data']['p']}\{api['data']['mp']}\n今日查询最高在线:{api['data']['today_max']}\n"),
            Comp.Plain(f"今日查询最低在线:{api['data']['today_min']}\n"),
            Comp.Plain(f"历史查询最高在线:{api['data']['history_max']}\n"),
            Comp.Plain(f"总查询次数:{api['data']['total_queries']}\n"),
            Comp.Plain(f"网络延迟:{api['data']['ping']}")
        ]
        yield event.chain_result(chain)

        if temp_file_path:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    @filter.command("register")
    async def register_server(self, event: AstrMessageEvent, server_info: str):
        """注册服务器配置，格式：/register [ip]:[端口]"""
        session_id = event.get_session_id()
        
        if ":" not in server_info:
            yield event.plain_result("格式错误！请使用：/register [ip]:[端口]")
            return
        
        try:
            ip, port = server_info.split(":", 1)
            ip = ip.strip()
            port = port.strip()
            
            if not ip or not port:
                yield event.plain_result("格式错误！IP地址和端口不能为空")
                return
            
            api_url = f"https://www.minecraftservers.cn/api/query?ip={ip}%3A{port}"
            self.user_configs[session_id] = {"ip": ip, "port": port}
            yield event.plain_result(f"配置完成，API链接为：\n{api_url}")
        except Exception as e:
            yield event.plain_result(f"配置失败：{str(e)}")

    @filter.command("query")
    async def query_config(self, event: AstrMessageEvent):
        """查询已配置的API链接"""
        session_id = event.get_session_id()
        if session_id in self.user_configs:
            ip = self.user_configs[session_id]["ip"]
            port = self.user_configs[session_id]["port"]
            api_url = f"https://www.minecraftservers.cn/api/query?ip={ip}%3A{port}"
            yield event.plain_result(f"API链接为：\n{api_url}")
        else:
            yield event.plain_result("无")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
