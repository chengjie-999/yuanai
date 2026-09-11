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

from api.v1.db_helpers import get_db as _get_db, verify_session_owner as _verify_session_owner, SAFE_ERROR as _SAFE_ERROR
from api.v1.middleware import get_user_id as _get_user_id

_RTC_API_HOST = "rtc.volcengineapi.com"
_RTC_API_URL = f"https://{_RTC_API_HOST}"
_ACTION_VERSION = "2024-12-01"
_TIMEOUT = 10  # OpenAPI 调用超时（秒）

# 语音对话系统提示词（口语化，避免冗长输出）
_SYSTEM_PROMPT = (
    "你是小元，用户的语音助手，与用户进行自然、简洁的中文口语对话。"
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


def _build_start_body(app_id: str, room_id: str, task_id: str, rtc_user_id: str) -> dict:
    """构造 StartVoiceChat 请求体（对齐官方 rtc-server-demo-open 1201 大模型模板）"""
    from config.settings import (
        VOICE_LLM_ENDPOINT_ID,
        VOICE_ASR_APP_ID, VOICE_ASR_ACCESS_TOKEN, VOICE_ASR_RESOURCE_ID,
        VOICE_TTS_APP_ID, VOICE_TTS_ACCESS_TOKEN, VOICE_TTS_VOICE_BOT,
    )
    config: dict = {}
    if VOICE_ASR_APP_ID and VOICE_ASR_ACCESS_TOKEN:
        config["ASRConfig"] = {
            "Provider": "volcano",
            "VolumeGain": 1,
            "ProviderParams": {
                "Mode": "bigmodel",
                "AppId": VOICE_ASR_APP_ID,
                "AccessToken": VOICE_ASR_ACCESS_TOKEN,
                "ApiResourceId": VOICE_ASR_RESOURCE_ID,
                "StreamMode": 1,
                "end_window_size": 500,
                "force_to_speech_time": 500,
            },
        }
    if VOICE_TTS_APP_ID and VOICE_TTS_ACCESS_TOKEN:
        config["TTSConfig"] = {
            "IgnoreBracketText": [1, 2, 3, 4, 5],
            "Provider": "volcano_bidirection",
            "ProviderParams": {
                "app": {"appid": VOICE_TTS_APP_ID, "token": VOICE_TTS_ACCESS_TOKEN},
                "audio": {"voice_type": VOICE_TTS_VOICE_BOT, "pitch_rate": 1, "speech_rate": 1},
                "ResourceId": "volc.service_type.10029",
            },
        }
    if VOICE_LLM_ENDPOINT_ID:
        config["LLMConfig"] = {
            "Mode": "ArkV3",
            "EndPointId": VOICE_LLM_ENDPOINT_ID,
            "MaxTokens": 1024,
            "Temperature": 0.1,
            "TopP": 0.3,
            "Prefill": True,
            # 实测为字符串数组 []string
            "SystemMessages": [_SYSTEM_PROMPT],
            "HistoryLength": 3,
        }
    return {
        "AppId": app_id,
        "RoomId": room_id,
        "TaskId": task_id,
        "Config": config,
        "AgentConfig": {
            "BotName": "小元",
            # UserID 必须显式提供（实测为空时校验失败），沿用官方默认规则 voiceChat_{TaskId}
            "UserID": f"voiceChat_{task_id}",
            # TargetUserID：智能体交互对象（客户端 UserId），字符串数组且仅支持一个（实测必填）
            "TargetUserID": [rtc_user_id],
            "WelcomeMessage": "你好，我是小元，有什么可以帮你的吗？",
        },
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


class VoiceMessageRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="聊天会话 ID")
    role: str = Field(..., pattern="^(user|assistant)$", description="消息角色")
    content: str = Field(..., min_length=1, description="转录文本")


class VoiceTtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="要朗读的文本")
    sender: str = Field(None, description="消息归属 Agent（orchestrator/analysis/collection/automation/claude/local），缺省用默认音色")


@router.post("/start", response_model=VoiceStartResponse)
def start_voice_chat(req: VoiceStartRequest, request: Request):
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

        _call_rtc_api("StartVoiceChat", _build_start_body(app_id, room_id, task_id, rtc_user_id))
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
def end_voice_chat(req: VoiceEndRequest, request: Request):
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


@router.post("/message")
def append_voice_message(req: VoiceMessageRequest, request: Request):
    """语音对话转录消息逐条追加到聊天会话（不动现有消息，首条用户消息自动定标题）"""
    try:
        db = _get_db()
        user_id = _get_user_id(request)
        _verify_session_owner(db, req.session_id, user_id)
        db.add_chat(req.session_id, req.role, req.content)
        from db.cache import clear_chat_cache
        clear_chat_cache(req.session_id)
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("追加语音转录消息失败: %s", e)
        raise HTTPException(status_code=500, detail=_SAFE_ERROR)


@router.post("/tts")
def voice_tts(req: VoiceTtsRequest, request: Request):
    """文字转语音（消息气泡「朗读」按钮）：调用豆包语音合成大模型 2.0，按消息归属 Agent 选音色"""
    from config.settings import VOICE_TTS_APP_ID, VOICE_TTS_ACCESS_TOKEN, VOICE_TTS_VOICE, AGENT_VOICE_MAP
    from fastapi.responses import Response
    if not (VOICE_TTS_APP_ID and VOICE_TTS_ACCESS_TOKEN):
        raise HTTPException(status_code=503, detail="语音合成未配置：请先配置 VOICE_TTS_* 凭据")
    try:
        # 音色按 Agent 查表（用户设置页可改），未知 sender 回退 env 默认音色
        speaker = AGENT_VOICE_MAP.get(req.sender, VOICE_TTS_VOICE) if req.sender else VOICE_TTS_VOICE
        body = {
            "user": {"uid": f"tts_{getattr(request.state, 'user_id', 0)}"},
            "req_params": {
                "text": req.text,
                "speaker": speaker,
                "audio_params": {"format": "mp3", "sample_rate": 24000},
            },
        }
        headers = {
            "X-Api-App-Key": VOICE_TTS_APP_ID,
            "X-Api-Access-Key": VOICE_TTS_ACCESS_TOKEN,
            # 语音合成大模型 2.0（音色须为 2.0 系列，如 zh_female_xiaohe_uranus_bigtts）
            "X-Api-Resource-Id": "seed-tts-2.0",
            "X-Api-Request-Id": uuid.uuid4().hex,
            "X-Api-Connect-Id": uuid.uuid4().hex,
            "Content-Type": "application/json",
        }
        url = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
        r = urllib.request.Request(
            url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers, method="POST",
        )
        with urllib.request.urlopen(r, timeout=20) as resp:
            raw = resp.read()
        # 响应为换行分隔的 JSON 流：每段 {"code":0,"data":"<base64 音频片段>"}，
        # 末尾 {"code":20000000,"message":"OK","data":null} 结束标记
        import base64
        audio_parts = []
        for line in raw.split(b"\n"):
            line = line.strip()
            if not line or line[:1] != b"{":
                continue
            try:
                payload = json.loads(line.decode("utf-8"))
            except Exception:
                continue
            code = payload.get("code")
            if code is None:
                continue
            if code == 20000000:
                break  # 正常结束标记
            if code != 0:
                err = json.dumps(payload, ensure_ascii=False)[:300]
                logger.error("TTS 合成失败: %s", err)
                raise HTTPException(status_code=502, detail=f"语音合成失败：{err}")
            if payload.get("data"):
                try:
                    audio_parts.append(base64.b64decode(payload["data"]))
                except Exception:
                    # 单个坏分片跳过，不因一段损坏丢弃已合成的完整音频
                    logger.warning("TTS 音频分片 base64 解码失败，跳过该段")
        if not audio_parts:
            raise HTTPException(status_code=502, detail="语音合成失败：未返回音频")
        return Response(content=b"".join(audio_parts), media_type="audio/mpeg")
    except HTTPException:
        raise
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        logger.error("TTS 合成失败(%s): %s", e.code, detail)
        raise HTTPException(status_code=502, detail=f"语音合成失败（{e.code}）：{detail}")
    except Exception as e:
        logger.error("TTS 合成异常: %s", e)
        raise HTTPException(status_code=500, detail="语音合成服务不可用，请稍后重试")
