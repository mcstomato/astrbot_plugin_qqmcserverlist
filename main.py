from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import requests
import json

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
        user_name = event.get_sender_name()
        message_str = event.message_str
        message_chain = event.get_messages()
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!")

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
            
            api_url = f"https://api.miri.site/mcPlayer/get.php?ip={ip}&port={port}"
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
            api_url = f"https://api.miri.site/mcPlayer/get.php?ip={ip}&port={port}"
            yield event.plain_result(f"API链接为：\n{api_url}")
        else:
            yield event.plain_result("无")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
