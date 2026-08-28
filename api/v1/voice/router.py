"""语音对话 API（火山引擎 RTC + 豆包 ASR/TTS + 方舟 LLM）

流程：
1. 前端点击 🎙️ → POST /voice/start → 服务端创建 room/task 并调用 StartVoiceChat
   启动 AI 智能体入房，同时签发进房 Token 返回前端
2. 前端加载 @volcengine/rtc SDK → joinRoom → 采集麦克风发布 → 订阅机器人音频
3. 挂断 → POST /voice/end → StopVoiceChat 停止任务（180s 无真人自动停止，及时调用避免计费）

接口：https://rtc.volcengineapi.com?Action=StartVoiceChat&Version=2024-12-01（V4 签名）
注意：字段以官方 2024-12-01 版本文档为准，首次上线联调时对照控制台核对。
"""

import json
import logging
import uuid
import urllib.request
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.v1.voice.rtc_token import generate_rtc_token
from api.v1.voice.v4_sign import v4_sign_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])

_RTC_API_HOST = "rtc.volcengineapi.com"
_RTC_API_URL = f"https://{_RTC_API_HOST}"
_ACTION_VERSION = "2024-12-01"
_TIMEOUT = 10  # OpenAPI 调用超时（秒）

# 语音对话系统提示词（口语化，避免冗长输出）
_SYSTEM_PROMPT = (
    "你是小元AI的语音助手，与用户进行自然、简洁的中文口语对话。"
    "回答尽量简短直接，一句话能说清的不说两句；遇到需要分析数据、"
    "采集网页或自动化操作的任务时，说明你会在文字对话中继续处理。"
)


def _voice_configured() -> bool:
    from config.settings import (
        VOLCANO_ACCESS_KEY, VOLCANO_SECRET_KEY,
        VOLCANO_RTC_APP_ID, VOLCANO_RTC_APP_KEY,
    )
    return all([VOLCANO_ACCESS_KEY, VOLCANO_SECRET_KEY, VOLCANO_RTC_APP_ID, VOLCANO_RTC_APP_KEY])


def _call_rtc_api(action: str, body: dict) -> dict:
    """调用 RTC OpenAPI（V4 签名），返回响应 JSON；失败抛 HTTPException"""
    from config.settings import VOLCANO_ACCESS_KEY, VOLCANO_SECRET_KEY
    payload = json.dumps(body, ensure_ascii=False)
    query = {"Action": action, "Version": _ACTION_VERSION}
    headers = v4_sign_request(
        access_key=VOLCANO_ACCESS_KEY,
        secret_key=VOLCANO_SECRET_KEY,
        method="POST",
        host=_RTC_API_HOST,
        uri="/",
        query=query,
        payload=payload,
    )
    url = _RTC_API_URL + "?Action=" + action + "&Version=" + _ACTION_VERSION
    try:
        req = urllib.request.Request(url, data=payload.encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        logger.error("RTC OpenAPI %s 失败: %s %s", action, e.code, detail)
        raise HTTPException(status_code=502, detail=f"语音服务调用失败（{e.code}）：{detail}")
    except Exception as e:
        logger.error("RTC OpenAPI %s 异常: %s", action, e)
        raise HTTPException(status_code=502, detail="语音服务不可用，请稍后重试")
    # 非 success 响应：提取火山 API 错误信息
    result = data.get("ResponseMetadata", {})
    if data.get("Result") != "success" and result.get("Error"):
        err = result["Error"]
        logger.error("RTC OpenAPI %s 业务失败: %s", action, err)
        raise HTTPException(status_code=502, detail=f"语音服务业务错误：{err.get('Message', '未知错误')}")
    return data


def _build_start_body(app_id: str, room_id: str, task_id: str) -> dict:
    """构造 StartVoiceChat 请求体（字段对应 2024-12-01 版本）"""
    from config.settings import (
        VOICE_LLM_ENDPOINT_ID, VOICE_LLM_MODEL,
        VOICE_ASR_APP_ID, VOICE_ASR_ACCESS_TOKEN,
        VOICE_TTS_APP_ID, VOICE_TTS_ACCESS_TOKEN, VOICE_TTS_VOICE,
    )
    config: dict = {}
    if VOICE_ASR_APP_ID and VOICE_ASR_ACCESS_TOKEN:
        config["ASRConfig"] = {
            "Provider": "volcano",
            "ProviderParams": {
                "Mode": "bigmodel",
                "Credential": {"AppId": VOICE_ASR_APP_ID, "AccessToken": VOICE_ASR_ACCESS_TOKEN},
            },
        }
    if VOICE_LLM_ENDPOINT_ID:
        config["LLMConfig"] = {
            "Mode": "ArkV3",
            "EndPointId": VOICE_LLM_ENDPOINT_ID,
            "ModelName": VOICE_LLM_MODEL or "",
            "Temperature": 0.7,
            "HistoryLength": 10,
            "SystemMessages": [{"Role": "system", "Content": _SYSTEM_PROMPT}],
        }
    if VOICE_TTS_APP_ID and VOICE_TTS_ACCESS_TOKEN:
        config["TTSConfig"] = {
            "Provider": "volcano",
            "ProviderParams": {
                "Credential": {"AppId": VOICE_TTS_APP_ID, "AccessToken": VOICE_TTS_ACCESS_TOKEN},
                "Voice": VOICE_TTS_VOICE,
            },
        }
    return {
        "AppId": app_id,
        "RoomId": room_id,
        "TaskId": task_id,
        "Config": config,
        "AgentConfig": {"BotName": "小元AI"},
    }


class VoiceStartRequest(BaseModel):
    pass


class VoiceStartResponse(BaseModel):
    app_id: str
    room_id: str
    user_id: str
    rtc_token: str
    task_id: str


class VoiceEndRequest(BaseModel):
    room_id: str = Field(..., min_length=1, description="房间 ID（start 时下发）")
    task_id: str = Field(..., min_length=1, description="任务 ID（start 时下发）")


@router.post("/start", response_model=VoiceStartResponse)
async def start_voice_chat(req: VoiceStartRequest, request: Request):
    """创建语音房间：启动 AI 智能体入房并签发进房 Token"""
    from config.settings import VOLCANO_RTC_APP_ID, VOLCANO_RTC_APP_KEY
    if not _voice_configured():
        raise HTTPException(
            status_code=503,
            detail="语音功能未配置：请先在服务器 .env 中配置 VOLCANO_* 凭据",
        )
    try:
        app_id = VOLCANO_RTC_APP_ID
        room_id = uuid.uuid4().hex
        user_id = getattr(request.state, "user_id", None) or 0
        task_id = uuid.uuid4().hex
        # user_id 作为流 ID 的一部分需稳定字符串
        rtc_user_id = f"user{user_id}"

        _call_rtc_api("StartVoiceChat", _build_start_body(app_id, room_id, task_id))
        token = generate_rtc_token(
            app_id=app_id,
            app_key=VOLCANO_RTC_APP_KEY,
            room_id=room_id,
            user_id=rtc_user_id,
        )
        return VoiceStartResponse(
            app_id=app_id, room_id=room_id, user_id=rtc_user_id,
            rtc_token=token, task_id=task_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("启动语音对话失败: %s", e)
        raise HTTPException(status_code=500, detail="语音服务启动失败，请稍后重试")


@router.post("/end")
async def end_voice_chat(req: VoiceEndRequest, request: Request):
    """结束语音对话：停止 AI 智能体任务"""
    from config.settings import VOLCANO_RTC_APP_ID
    if not _voice_configured():
        raise HTTPException(status_code=503, detail="语音功能未配置")
    try:
        _call_rtc_api("StopVoiceChat", {
            "AppId": VOLCANO_RTC_APP_ID,
            "RoomId": req.room_id,
            "TaskId": req.task_id,
        })
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("结束语音对话失败: %s", e)
        raise HTTPException(status_code=500, detail="语音服务停止失败，请稍后重试")
