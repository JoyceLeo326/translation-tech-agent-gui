"""会话级音频URL存储工具

用于在工作流中存储模式一上传的音频URL，并在模式二中自动查询复用。
"""
import os
import datetime
from typing import Optional

from postgrest.exceptions import APIError

# 获取Supabase客户端
try:
    from storage.database.supabase_client import get_supabase_client
    _supabase_available = True
except Exception:
    _supabase_available = False


def _get_client():
    """获取Supabase客户端,失败抛出异常"""
    if not _supabase_available:
        raise Exception("Supabase客户端未初始化,请确认环境变量和服务状态")
    return get_supabase_client()


def save_audio_url(session_id: str, audio_url: str, file_type: str = "audio") -> None:
    """
    存储会话级音频URL

    Args:
        session_id: 会话ID,用于区分不同用户
        audio_url: 音频文件URL
        file_type: 文件类型,默认audio
    """
    if not session_id or not audio_url:
        raise Exception("session_id和audio_url不能为空")

    client = _get_client()
    try:
        # 使用upsert确保幂等
        client.table("audio_session").upsert(
            {
                "session_id": session_id,
                "audio_url": audio_url,
                "file_type": file_type,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            on_conflict="session_id"
        ).execute()
    except APIError as e:
        raise Exception(f"存储音频URL失败: {e.message}")


def get_latest_audio_url() -> Optional[str]:
    """
    获取最近一次存储的音频URL

    Returns:
        最近一次存储的音频URL,如果没有则返回None
    """
    client = _get_client()
    try:
        response = (
            client.table("audio_session")
            .select("audio_url, file_type")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        data = response.data
        if data and len(data) > 0:
            record = data[0]
            if isinstance(record, dict):
                return record.get("audio_url")
        return None
    except APIError as e:
        raise Exception(f"查询音频URL失败: {e.message}")


def get_audio_url_by_session(session_id: str) -> Optional[str]:
    """
    根据会话ID获取音频URL

    Args:
        session_id: 会话ID

    Returns:
        指定会话的音频URL,如果没有则返回None
    """
    if not session_id:
        return None

    client = _get_client()
    try:
        response = (
            client.table("audio_session")
            .select("audio_url, file_type")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        if response is None:
            return None
        data = response.data
        if isinstance(data, dict):
            return data.get("audio_url")
        return None
    except APIError as e:
        raise Exception(f"查询音频URL失败: {e.message}")
