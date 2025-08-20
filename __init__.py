"""
Nekro Plugin - memU.so 长期记忆（memu_memory）

为 NekroAgent 提供长期记忆能力：写入记忆、自动回忆提示注入、主动回忆检索。
参考封装风格：Jerry-FaGe/nekro-plugin-anime-tts
"""

import logging
from typing import Optional

from pydantic import Field, field_validator

from nekro_agent.api import schemas
from nekro_agent.api.plugin import ConfigBase, NekroPlugin, SandboxMethodType

try:
    from memu import MemuClient
except ImportError as e:
    raise ImportError("缺少依赖 memu-py，请先安装：pip install --upgrade memu-py") from e


plugin = NekroPlugin(
    name="智能记忆插件 (memU.so)",
    module_name="memu_memory",
    description="通过 memU.so 官方 API 提供长期记忆能力，支持多人设和自动回忆。",
    version="1.0.0",
    author="johntime",
    url="https://github.com/KroMiose/nekro-agent",
)

logger = logging.getLogger(__name__)


@plugin.mount_config()
class MemUConfig(ConfigBase):
    """memU.so 插件配置"""

    MEMU_API_KEY: str = Field(default="", title="memU.so API Key")
    BASE_URL: str = Field(default="https://api.memu.so", title="memU.so API 地址")
    AGENT_ID: str = Field(default="nekro_agent", title="默认助理ID")
    AGENT_NAME: str = Field(default="Nekro Assistant", title="默认助理名称")
    RECALL_TOP_K: int = Field(
        default=3,
        title="自动回忆数量",
        description="每次对话时，自动从记忆库中检索并注入到提示词中的最相关记忆的数量。设为 0 可禁用此功能。",
    )

    @field_validator("MEMU_API_KEY", mode="before")
    @classmethod
    def _validate_api_key(cls, v):
        if v is None:
            return ""
        return v


config = plugin.get_config(MemUConfig)
memu_client: Optional[MemuClient] = None


async def _initialize_client_if_needed() -> None:
    """如果客户端未初始化，则进行初始化"""
    global memu_client
    if memu_client is not None:
        return

    current_config = plugin.get_config(MemUConfig)
    if not current_config.MEMU_API_KEY:
        logger.error("MemU API Key 未在插件配置中设置。请在插件设置页面输入您的 API Key。")
        return

    logger.info("首次调用，开始初始化 MemUClient...")
    try:
        memu_client = MemuClient(
            base_url=current_config.BASE_URL,
            api_key=current_config.MEMU_API_KEY,
        )
        logger.info("MemUClient (memu.so) 初始化成功。")
    except Exception as e:
        logger.error(f"MemUClient 初始化失败: {e}", exc_info=True)


@plugin.mount_prompt_inject_method("relevant_memories_from_memu_so")
async def inject_relevant_memories(_ctx: schemas.AgentCtx) -> str:
    """自动回忆注入（Prompt Injection）

    根据最近对话消息语境，调用 memu.so 检索相关记忆，并返回一段可直接拼接到系统提示的文本。
    当未配置 API Key、`RECALL_TOP_K=0`、无可用历史或检索失败时返回空字符串，不影响对话正常生成。

    Returns:
        str: 以 "--- Relevant Memories Retrieved From Your Past ---" 开头的多行文本，每行以 "- " 列出一条记忆。
    """
    await _initialize_client_if_needed()

    current_config = plugin.get_config(MemUConfig)
    if not memu_client or current_config.RECALL_TOP_K == 0:
        return ""

    try:
        recent_history = [f"{msg.role}: {msg.content}" for msg in _ctx.message_history[-4:]]
        query_text = "\n".join(recent_history)
        if not query_text:
            return ""

        retrieved_response = memu_client.retrieve_related_memory_items(
            query=query_text,
            user_id=_ctx.from_chat_key,
            top_k=current_config.RECALL_TOP_K,
        )

        if not retrieved_response or not retrieved_response.related_memories:
            return ""

        prompt_lines = ["--- Relevant Memories Retrieved From Your Past ---"]
        for memory_item in retrieved_response.related_memories:
            prompt_lines.append(f"- {memory_item.memory.content}")

        logger.info(
            f"成功为 User '{_ctx.channel_name}' 注入了 {len(retrieved_response.related_memories)} 条相关记忆。"
        )
        return "\n".join(prompt_lines)
    except Exception as e:
        logger.warning(f"自动检索记忆时出错: {e}")
        return ""


@plugin.mount_sandbox_method(SandboxMethodType.BEHAVIOR, "记忆对话")
async def memorize_conversation(
    _ctx: schemas.AgentCtx,
    chat_key: str,
    conversation: str,
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    *args,
    **kwargs,
) -> str:
    """Memorize Conversation（写入长期记忆）

    将一段对话或信息片段存入 memu.so 长期记忆库，用于后续自动或主动回忆。
    典型用法：记录用户偏好、事实、关键事件、承诺事项等。支持通过 `agent_id/agent_name` 指定多人设。

    Args:
        _ctx (AgentCtx): 调用上下文（由系统注入）。
        chat_key (str): 当前聊天会话唯一标识。
        conversation (str): 需要被记住的文本内容。
        agent_id (Optional[str]): 可选，当前助理人设的 ID；未提供时使用插件配置默认值。
        agent_name (Optional[str]): 可选，当前助理人设的名称；未提供时使用插件配置默认值。

    Returns:
        str: 表示记忆任务执行结果的确认信息。

    Example:
        记忆对话(chat_key="session_123", conversation="用户最喜欢的颜色是蓝色。")
    """
    await _initialize_client_if_needed()
    if not memu_client:
        raise ConnectionError(
            "memu.so client is not initialized or failed to initialize. Please check the plugin configuration."
        )

    try:
        current_config = plugin.get_config(MemUConfig)
        final_agent_id = agent_id if agent_id is not None else current_config.AGENT_ID
        final_agent_name = agent_name if agent_name is not None else current_config.AGENT_NAME
        structured_conversation = [{"role": "user", "content": conversation}]

        memo_response = memu_client.memorize_conversation(
            conversation=structured_conversation,
            user_id=_ctx.from_chat_key,
            user_name=_ctx.channel_name,
            agent_id=final_agent_id,
            agent_name=final_agent_name,
        )

        logger.info(f"已成功提交记忆任务到 memu.so，Task ID: {memo_response.task_id}。")
        return f"✅ {final_agent_name} 已经收到指令，会把内容记下来的！"
    except Exception as e:
        logger.error(f"调用 memU.so 记忆服务时出错: {e}", exc_info=True)
        raise RuntimeError(f"Failed to memorize conversation: {type(e).__name__}: {e}")


@plugin.mount_sandbox_method(SandboxMethodType.TOOL, "回忆信息")
async def recall_memory(_ctx: schemas.AgentCtx, query: str) -> str:
    """Recall Memory（主动回忆检索）

    根据自然语言查询，在 memu.so 长期记忆库中检索最相关的信息条目并返回格式化文本。

    Args:
        _ctx (AgentCtx): 调用上下文（由系统注入）。
        query (str): 要检索的问题或主题，例如："用户最喜欢的颜色是什么？"。

    Returns:
        str: 多行文本，每行一条相关记忆；若没有匹配，则返回“在记忆中没有找到相关信息”。

    Example:
        回忆信息(query="用户最喜欢的颜色")
    """
    await _initialize_client_if_needed()
    if not memu_client:
        raise ConnectionError(
            "memu.so client is not initialized or failed to initialize. Please check the plugin configuration."
        )
    try:
        retrieved_response = memu_client.retrieve_related_memory_items(
            query=query, user_id=_ctx.from_chat_key, top_k=3
        )

        if not retrieved_response or not retrieved_response.related_memories:
            return "（在记忆中没有找到相关信息。）"

        response_text = "根据我的回忆，以下是与您问题最相关的信息：\n"
        for i, memory_item in enumerate(retrieved_response.related_memories):
            response_text += f"{i + 1}. {memory_item.memory.content}\n"
        return response_text
    except Exception as e:
        logger.error(f"主动检索记忆时出错: {e}", exc_info=True)
        raise RuntimeError(f"Failed to recall memory: {type(e).__name__}: {e}")


__all__ = ["plugin"]

