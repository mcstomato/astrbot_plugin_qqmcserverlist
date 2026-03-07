from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import requests
import json

@register("list", "MC_Stomato", "一个简单的服务器查询插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

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
        session_id = event.get_session_id()
        await self.context.set_session_data(session_id, "register_state", "waiting_ip")
        yield event.plain_result("请输入ip地址：")

    @filter.command("query")
    async def query_config(self, event: AstrMessageEvent):
        """查询已配置的API链接"""
        session_id = event.get_session_id()
        config = await self.context.get_session_data(session_id, "mc_server_config")
        if config:
            ip = config.get("ip")
            port = config.get("port")
            api_url = f"https://api.miri.site/mcPlayer/get.php?ip={ip}&port={port}"
            yield event.plain_result(f"API链接为：\n{api_url}")
        else:
            yield event.plain_result("无")

    @filter.command("input")
    async def handle_input(self, event: AstrMessageEvent, content: str):
        """处理注册流程中的输入"""
        session_id = event.get_session_id()
        register_state = await self.context.get_session_data(session_id, "register_state")

        if register_state == "waiting_ip":
            await self.context.set_session_data(session_id, "temp_ip", content)
            await self.context.set_session_data(session_id, "register_state", "waiting_port")
            yield event.plain_result("请输入端口号：")

        elif register_state == "waiting_port":
            ip = await self.context.get_session_data(session_id, "temp_ip")
            port = content
            api_url = f"https://api.miri.site/mcPlayer/get.php?ip={ip}&port={port}"
            await self.context.set_session_data(session_id, "mc_server_config", {"ip": ip, "port": port})
            await self.context.set_session_data(session_id, "register_state", None)
            yield event.plain_result(f"配置完成，API链接为：\n{api_url}")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
