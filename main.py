from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp
import os
import tempfile
import base64
import requests
import json
from functools import wraps
import mcrcon

# ==================== 权限配置中心 ====================
# 在这里统一管理所有命令的权限
COMMAND_PERMISSIONS = {
    # 命令名: 需要的权限级别
    # "admin" - 仅群管理员可用
    # "all" - 所有人可用
    "info": "all",           # 查询服务器信息
    "rank": "all",           # 查询服务器信息
    "query": "admin",          # 查询已配置的API链接
    "register": "admin",         # 注册服务器配置（所有人可用）
    "addadmin": "admin",       # 添加机器人管理员
    "deladmin": "admin",       # 移除机器人管理员
    "listadmin": "admin",      # 查看机器人管理员列表
    "command": "admin",      # 向服务器发送命令
    "list": "all",           # 查询服务器玩家列表
    "group": "admin",        # 群组消息可视选项
}

# 机器人管理员列表（用户ID）
BOT_ADMIN_USERS = set()
# ====================================================

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


def require_permission(command_name: str):
    """
    权限检查装饰器
    根据 COMMAND_PERMISSIONS 配置自动检查权限
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, event: AstrMessageEvent, *args, **kwargs):
            # 检查群聊白名单
            if self.allowed_groups:
                group_id = event.get_group_id()
                if group_id and group_id not in self.allowed_groups:
                    yield event.plain_result("该群聊未授权使用此插件")
                    return
            
            # 获取命令权限配置
            permission = COMMAND_PERMISSIONS.get(command_name, "all")
            
            # 如果需要管理员权限
            if permission == "admin":
                # 检查是否是群管理员
                if event.role != "admin":
                    # 检查是否是机器人管理员
                    user_id = event.get_sender_id()
                    if user_id not in BOT_ADMIN_USERS:
                        yield event.plain_result("权限不足！只有群管理员或机器人管理员可以使用此命令。")
                        return
            
            # 权限检查通过，执行原函数
            async for result in func(self, event, *args, **kwargs):
                yield result
        return wrapper
    return decorator


@register("list", "MC_Stomato", "一个简单的服务器查询插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.user_configs = {}
        # 存储最新的消息信息
        self.latest_message = {"sender": "", "content": ""}
        # 存储群组消息可视选项配置
        self.group_settings = {}
        # 解析允许的群聊ID
        allowed_groups_str = self.config.get("allowed_groups", "")
        self.allowed_groups = set()
        if allowed_groups_str:
            self.allowed_groups = set(group.strip() for group in allowed_groups_str.split(",") if group.strip())
        logger.info(f"群聊白名单已加载: {self.allowed_groups}")

    @filter.command("info")
    @require_permission("info")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 info 指令"""
        session_id = event.get_session_id()
        
        if session_id not in self.user_configs:
            yield event.plain_result("请先获取ip端口")
            return
        
        ip = self.user_configs[session_id]["ip"]
        port = self.user_configs[session_id]["port"]
        api_url = f"https://www.minecraftservers.cn/api/query?ip={ip}%3A{port}"
        api_url2 = f"https://api.miri.site/mcPlayer/get.php?ip={ip}&port={port}"
        
        temp_file_path = None
        
        try:
            # 设置10秒超时，同时请求两个 API
            response = requests.get(api_url, timeout=10)
            response2 = requests.get(api_url2, timeout=10)
            api = response.json()
            api2 = response2.json()

            # 处理 logo 图片
            logo_data = api['data'].get('logo')
            if logo_data:
                # 保存 Base64 到临时文件
                temp_file_path = save_base64_to_temp(logo_data)

            # 提取所有玩家 name
            player_names = []
            if 'sample' in api2:
                for player in api2['sample']:
                    player_names.append(player.get('name', ''))
            players_str = ', '.join(player_names) if player_names else '无'

            chain = [
                Comp.Image.fromFileSystem(temp_file_path) if temp_file_path else Comp.Plain("无logo"),
                Comp.Plain(
                        f"motd:{api['data']['motd']}\n"
                        f"玩家人数:{api['data']['p']}\{api['data']['mp']}\n"
                        f"今日查询最高在线:{api['data']['today_max']}\n"
                        f"今日查询最低在线:{api['data']['today_min']}\n"
                        f"历史查询最高在线:{api['data']['history_max']}\n"
                        f"查询次数:{api['data']['total_queries']}\n"
                        f"网络延迟:{api['data']['ping']}"
                        )
            ]
            yield event.chain_result(chain)

        except requests.exceptions.Timeout:
            yield event.plain_result("获取失败：请求超时（超过10秒）")
        except requests.exceptions.RequestException as e:
            yield event.plain_result(f"获取失败：网络连接错误\n{str(e)}")
        except json.JSONDecodeError:
            yield event.plain_result("获取失败：API返回数据格式错误")
        except KeyError as e:
            yield event.plain_result(f"别试了，估计寄了")
        except Exception as e:
            yield event.plain_result(f"获取失败：{str(e)}")
        finally:
            # 清理临时文件
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    @filter.command("register")
    @require_permission("register")
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
    @require_permission("query")
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

    @filter.command("addadmin")
    @require_permission("addadmin")
    async def add_admin_command(self, event: AstrMessageEvent):
        """添加机器人管理员，格式：/addadmin [用户ID] 或 /addadmin @用户"""
        # 获取完整的消息文本
        full_message = event.message_str.strip()
        
        # 提取参数部分（去掉 addadmin 前缀）
        if full_message.startswith('addadmin '):
            params = full_message[8:].strip()  # 8是"addadmin "的长度
        else:
            params = ""
        
        if not params:
            yield event.plain_result("请提供要添加的用户ID，格式：/addadmin [用户ID] 或 /addadmin @用户")
            return
        
        # 处理@用户格式
        user_id = params
        # 处理格式：[At:2186476377]
        if '[At:' in params and ']' in params:
            # 提取QQ号，格式如：[At:2186476377]
            start_idx = params.find('[At:') + 4  # 4是"[At:"的长度
            end_idx = params.find(']')
            if start_idx < end_idx:
                user_id = params[start_idx:end_idx]
        # 处理格式：@昵称[123456789]
        elif '[' in params and ']' in params:
            # 提取QQ号，格式如：@昵称[123456789]
            start_idx = params.find('[') + 1
            end_idx = params.find(']')
            if start_idx < end_idx:
                user_id = params[start_idx:end_idx]
        # 确保只保留数字部分
        user_id = ''.join([c for c in user_id if c.isdigit()])
        
        BOT_ADMIN_USERS.add(user_id)
        yield event.plain_result(f"已添加机器人管理员：{user_id}")

    @filter.command("deladmin")
    @require_permission("deladmin")
    async def del_admin_command(self, event: AstrMessageEvent):
        """移除机器人管理员，格式：/deladmin [用户ID] 或 /deladmin @用户"""
        # 获取完整的消息文本
        full_message = event.message_str.strip()
        
        # 提取参数部分（去掉 deladmin 前缀）
        if full_message.startswith('deladmin '):
            params = full_message[8:].strip()  # 8是"deladmin "的长度
        else:
            params = ""
        
        if not params:
            yield event.plain_result("请提供要移除的用户ID，格式：/deladmin [用户ID] 或 /deladmin @用户")
            return
        
        # 处理@用户格式
        user_id = params
        # 处理格式：[At:2186476377]
        if '[At:' in params and ']' in params:
            # 提取QQ号，格式如：[At:2186476377]
            start_idx = params.find('[At:') + 4  # 4是"[At:"的长度
            end_idx = params.find(']')
            if start_idx < end_idx:
                user_id = params[start_idx:end_idx]
        # 处理格式：@昵称[123456789]
        elif '[' in params and ']' in params:
            # 提取QQ号，格式如：@昵称[123456789]
            start_idx = params.find('[') + 1
            end_idx = params.find(']')
            if start_idx < end_idx:
                user_id = params[start_idx:end_idx]
        # 确保只保留数字部分
        user_id = ''.join([c for c in user_id if c.isdigit()])
        
        BOT_ADMIN_USERS.discard(user_id)
        yield event.plain_result(f"已移除机器人管理员：{user_id}")

    @filter.command("listadmin")
    @require_permission("listadmin")
    async def list_admin_command(self, event: AstrMessageEvent):
        """查看机器人管理员列表"""
        if BOT_ADMIN_USERS:
            admin_list = "\n".join(BOT_ADMIN_USERS)
            yield event.plain_result(f"机器人管理员列表：\n{admin_list}")
        else:
            yield event.plain_result("当前没有机器人管理员")

    @filter.command("command")
    @require_permission("command")
    async def command_command(self, event: AstrMessageEvent):
        """向服务器发送命令，格式：/command [命令]"""
        # 获取完整的消息文本
        full_message = event.message_str.strip()
        
        # 调试日志
        logger.info(f"完整消息: {full_message}")
        
        # 提取命令部分（去掉 command 前缀）
        if full_message.startswith('command '):
            command = full_message[8:].strip()  # 8是"command "的长度
        else:
            command = ""
        
        logger.info(f"提取的命令: '{command}'")
        
        # 获取 RCON 配置
        rcon_address = self.config.get("rcon_address", "")
        rcon_port = self.config.get("rcon_port", 25575)
        rcon_password = self.config.get("rcon_password", "")
        
        if not rcon_address or not rcon_password:
            yield event.plain_result("RCON 配置不完整，请在插件设置中配置 RCON 地址和密码")
            return
        
        if not command:
            yield event.plain_result("请提供要发送的命令，格式：/command [命令]")
            return
        
        try:
            logger.info(f"正在连接 RCON: {rcon_address}:{rcon_port}")
            with mcrcon.MCRcon(rcon_address, rcon_password, rcon_port) as mcr:
                logger.info(f"发送命令: {command}")
                response = mcr.command(command)
                logger.info(f"RCON 响应: {response}")
                
                if response:
                    yield event.plain_result(f"命令执行结果：\n{response}")
                else:
                    yield event.plain_result("命令执行成功（无返回结果）")
                    
        except Exception as e:
            logger.error(f"RCON 执行失败: {e}", exc_info=True)
            yield event.plain_result(f"RCON 命令执行失败：{str(e)}")


    @filter.command("rank")
    @require_permission("rank")
    async def server_rank(self, event: AstrMessageEvent):
        '''这是一个 服务器排行榜 指令''' # 这是 handler 的描述，将会被解析方便用户了解插件内容。非常建议填写。
        message_str = event.message_str.strip() # 获取消息的纯文本内容
        logger.info("触发服务器排行榜指令!")
        
        rcon_address = self.config.get("rcon_address", "")
        rcon_port = self.config.get("rcon_port", 25575)
        rcon_password = self.config.get("rcon_password", "")
        
        if not rcon_address or not rcon_password:
            yield event.plain_result("RCON 配置不完整，请在插件设置中配置 RCON 地址和密码")
            return
        
        if not message_str:
            yield event.plain_result("请提供要发送的命令，格式：/rank [榜单名]")
            return
        
        # 提取榜单名
        rank_name = message_str
        if rank_name.startswith('rank '):
            rank_name = rank_name[5:].strip()  # 5是"rank "的长度
        else:
            rank_name = ""
        # 映射榜单名到 RCON 命令
        rcon_command = ""
        if rank_name == "死亡榜":
            rcon_command = "leaderboard deaths"
        elif rank_name == "在线时长":
            rcon_command = "leaderboard time_played"
        elif rank_name == "伤害":
            rcon_command = "leaderboard damage_dealt"
        else:
            yield event.plain_result(f"不支持的榜单名：{rank_name}")
            return

        try:
            logger.info(f"正在连接 RCON: {rcon_address}:{rcon_port}")
            with mcrcon.MCRcon(rcon_address, rcon_password, rcon_port) as mcr:
                logger.info(f"发送命令: {rcon_command}")
                response = mcr.command(rcon_command)
                logger.info(f"RCON 响应: {response}")
                
                if response:
                    yield event.plain_result(f"{response}")
                else:
                    yield event.plain_result("命令执行成功（无返回结果）")
                    
        except Exception as e:
            logger.error(f"RCON 执行失败: {e}", exc_info=True)
            yield event.plain_result(f"RCON 命令执行失败：{str(e)}")

    @filter.command("list")
    @require_permission("list")
    async def server_play_list(self, event: AstrMessageEvent):
        '''这是一个 服务器玩家列表 指令''' # 这是 handler 的描述，将会被解析方便用户了解插件内容。非常建议填写。
        logger.info("触发服务器玩家列表指令!")
        
        rcon_address = self.config.get("rcon_address", "")
        rcon_port = self.config.get("rcon_port", 25575)
        rcon_password = self.config.get("rcon_password", "")
        
        if not rcon_address or not rcon_password:
            yield event.plain_result("RCON 配置不完整，请在插件设置中配置 RCON 地址和密码")
            return
        
        try:
            logger.info(f"正在连接 RCON: {rcon_address}:{rcon_port}")
            with mcrcon.MCRcon(rcon_address, rcon_password, rcon_port) as mcr:
                logger.info(f"发送命令: list players")
                response = mcr.command("list")
                logger.info(f"RCON 响应: {response}")
                
                if response:
                    # 解析响应格式："There are X of a max of Y players online: player1, player2"
                    try:
                        # 提取在线人数和玩家列表
                        if "There are" in response and "players online:" in response:
                            parts = response.split("players online: ")
                            if len(parts) == 2:
                                # 提取人数
                                count_part = parts[0].replace("There are ", "").strip()
                                player_count = count_part.split(" ")[0]  # 获取第一个数字
                                # 提取玩家列表
                                player_list = parts[1]
                                formatted_response = f"当前服务器有{player_count}名玩家：{player_list}"
                                yield event.plain_result(formatted_response)
                            else:
                                yield event.plain_result(f"{response}")
                        else:
                            yield event.plain_result(f"{response}")
                    except Exception:
                        # 如果解析失败，返回原始响应
                        yield event.plain_result(f"{response}")
                else:
                    yield event.plain_result("命令执行成功（无返回结果）")
                    
        except Exception as e:
            logger.error(f"RCON 执行失败: {e}", exc_info=True)
            yield event.plain_result(f"RCON 命令执行失败：{str(e)}")

    @filter.command("group")
    @require_permission("group")
    async def group(self, event: AstrMessageEvent):
        '''这是一个 群组消息可视选项 指令'''
        logger.info("触发群组消息指令!")
        # 获取完整的消息文本
        full_message = event.message_str.strip()
        # 调试日志
        logger.info(f"完整消息: {full_message}")
    
        # 去掉 group 前缀
        if full_message.startswith('group '):
            params = full_message[6:].strip()  # 6是"group "的长度
        else:
            params = ""
        
        # 检查参数是否为空
        if not params:
            yield event.plain_result("请提供要发送的命令，格式：/group [玩家ID] [T(开启)/F(关闭)]")
            return
        
        # 分割参数
        parts = params.split()
        
        # 检查参数数量
        if len(parts) < 2:
            yield event.plain_result("请提供要发送的命令，格式：/group [玩家ID] [T(开启)/F(关闭)]")
            return
        
        player_id = parts[0]
        tf_value = parts[1].upper()
        
        # 检查T/F参数是否有效
        if tf_value not in ['T', 'F']:
            yield event.plain_result("请提供要发送的命令，格式：/group [玩家ID] [T(开启)/F(关闭)]")
            return
        
        # 转换T/F为1/0
        group_value = 1 if tf_value == 'T' else 0
        
        # 保存到变量
        self.group_settings[player_id] = group_value
        
        logger.info(f"已保存玩家 {player_id} 的群组消息设置为: {group_value}")
        yield event.plain_result(f"已设置玩家 {player_id} 的群组消息可视选项为: {'开启' if group_value == 1 else '关闭'}")

        command = f"scoreboard players set {player_id} group {group_value}"
        # 获取 RCON 配置
        rcon_address = self.config.get("rcon_address", "")
        rcon_port = self.config.get("rcon_port", 25575)
        rcon_password = self.config.get("rcon_password", "")
        
        if not rcon_address or not rcon_password:
            yield event.plain_result("RCON 配置不完整，请在插件设置中配置 RCON 地址和密码")
            return
        
        if not command:
            yield event.plain_result("请提供要发送的命令，格式：/command [命令]")
            return
        
        try:
            logger.info(f"正在连接 RCON: {rcon_address}:{rcon_port}")
            with mcrcon.MCRcon(rcon_address, rcon_password, rcon_port) as mcr:
                logger.info(f"发送命令: {command}")
                response = mcr.command(command)
                logger.info(f"RCON 响应: {response}")
                    
        except Exception as e:
            logger.error(f"RCON 执行失败: {e}", exc_info=True)
            yield event.plain_result(f"RCON 命令执行失败：{str(e)}")
        
    
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息，存储非指令消息的发送者和内容"""
        # 检查是否在允许的群聊中
        if self.allowed_groups:
            group_id = event.get_group_id()
            if group_id and group_id not in self.allowed_groups:
                return
        
        message_content = event.message_str.strip()
        
        for cmd in COMMAND_PERMISSIONS.keys():
            if message_content.startswith(cmd + " ") or message_content == cmd:
                return
        
        # 获取发送者昵称
        sender_name = event.get_sender_name() or "未知用户"
        
        # 处理消息长度
        if len(message_content) > 50:
            message_content = message_content[:50] + "......"
        
        # 存储最新的消息信息
        self.latest_message = {
            "sender": sender_name,
            "content": message_content
        }
        
        rcon_address = self.config.get("rcon_address", "")
        rcon_port = self.config.get("rcon_port", 25575)
        rcon_password = self.config.get("rcon_password", "")
        
        if not rcon_address or not rcon_password:
            logger.info("RCON 配置不完整，请在插件设置中配置 RCON 地址和密码")
            return

        chat = f"tellraw @a[scores={{group=1}}] [\
            {{\"text\":\"[\",\"color\":\"white\"}},\
            {{\"text\":\"群组消息\",\"color\":\"#FFA500\"}},\
            {{\"text\":\"] \",\"color\":\"white\"}},\
            {{\"text\":\"<\",\"color\":\"white\"}},\
            {{\"text\":\"{sender_name}\",\"color\":\"green\"}},\
            {{\"text\":\">\",\"color\":\"white\"}},\
            {{\"text\":\":\"}},{{\"text\":\" {message_content}\"}}]"

        if message_content:
            try:
                with mcrcon.MCRcon(rcon_address, rcon_password, rcon_port) as mcr:
                    logger.info(f"发送命令: {chat}")
                    mcr.command(chat)
                        
            except Exception as e:
                logger.error(f"RCON 执行失败: {e}", exc_info=True)


        # 记录日志
        logger.info(f"存储最新消息 - 发送者: {sender_name}, 内容: {message_content}")
        
        # 不返回任何结果，避免干扰正常消息流程
        return

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时调用。"""
