from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import requests
import json

@register("list", "MC_Stomato", "一个简单的服务器查询插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.register_states = {}  # 存储用户注册状态: {user_id: {"state": "waiting_ip"|"waiting_port", "ip": ""}}
        self.user_configs = {}  # 存储用户配置: {user_id: {"ip": "", "port": ""}}

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
    async def register_server(self, event: AstrMessageEvent):
        """注册服务器配置"""
        user_id = event.get_sender_id()
        self.register_states[user_id] = {"state": "waiting_ip", "ip": ""}
        yield event.plain_result("请输入ip地址：")

    @filter.command("query")
    async def query_config(self, event: AstrMessageEvent):
        """查询已配置的API链接"""
        user_id = event.get_sender_id()
        if user_id in self.user_configs:
            ip = self.user_configs[user_id]["ip"]
            port = self.user_configs[user_id]["port"]
            api_url = f"https://api.miri.site/mcPlayer/get.php?ip={ip}&port={port}"
            yield event.plain_result(f"API链接为：\n{api_url}")
        else:
            yield event.plain_result("无")

    @filter.on_message
    async def handle_message(self, event: AstrMessageEvent):
        """处理普通消息，用于接收注册流程中的输入"""
        user_id = event.get_sender_id()
        message_str = event.message_str.strip()

        if user_id in self.register_states:
            state = self.register_states[user_id]["state"]

            if state == "waiting_ip":
                self.register_states[user_id]["ip"] = message_str
                self.register_states[user_id]["state"] = "waiting_port"
                yield event.plain_result("请输入端口号：")

            elif state == "waiting_port":
                ip = self.register_states[user_id]["ip"]
                port = message_str
                api_url = f"https://api.miri.site/mcPlayer/get.php?ip={ip}&port={port}"
                self.user_configs[user_id] = {"ip": ip, "port": port}
                yield event.plain_result(f"配置完成，API链接为：\n{api_url}")
                del self.register_states[user_id]

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
