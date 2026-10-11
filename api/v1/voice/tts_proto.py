"""TTS 流式帧协议（纯函数零依赖）— 气泡朗读链路专用

frame := kind(1B) | length(4B BE) | payload
  kind 0x01 = audio（mp3 分片，聚合到 ≥CHUNK_BYTES 再发一帧）
  kind 0x02 = error（payload = JSON {"code": n, "message": str}）
  kind 0x00 = end（正常结束标记，无 payload）

为什么要帧协议：原实现是裸 mp3 字节流，火山合成中途失败时只能静默
断流（HTTP 200 已发出），前端分不清「正常播完」与「中途失败」；且
逐 4096B 行产出的碎 chunk 是断续的根源之一。帧协议把错误显式化、
把分片边界显式化（前端只按整帧播放，段内不再任意字节切分）。

兼容：前端按首字节嗅探——0x00/0x01/0x02 走帧解析；0xFF（MP3 sync）
或 0x49（'I'，ID3）走旧裸音频路径。新旧前后端任意组合不崩。
"""

import json
import struct
from typing import Tuple

KIND_AUDIO = 0x01
KIND_ERROR = 0x02
KIND_END = 0x00

_HEADER = struct.Struct(">BI")  # kind(1B) + length(4B big-endian)


def pack_frame(kind: int, payload: bytes = b"") -> bytes:
    """打包一帧：kind(1B) | length(4B BE) | payload"""
    return _HEADER.pack(kind, len(payload)) + payload


def pack_error(code: int, message: str) -> bytes:
    """错误帧（JSON payload）"""
    return pack_frame(KIND_ERROR,
                      json.dumps({"code": code, "message": message},
                                 ensure_ascii=False).encode("utf-8"))


def pack_end() -> bytes:
    return pack_frame(KIND_END)


def iter_frames(buf: bytes) -> Tuple[list, bytes]:
    """拆帧 → ([(kind, payload), ...], 残余字节)；跨 read 拼接用残余续传。

    单帧损坏时从下一个 0x00/0x01/0x02 疑似头重新同步（length 合法性校验），
    防止一个坏帧卡死整条流。
    """
    frames = []
    pos = 0
    n = len(buf)
    while pos + 5 <= n:
        kind = buf[pos]
        if kind not in (KIND_AUDIO, KIND_ERROR, KIND_END):
            pos += 1  # 字节错位：滑动一个字节重新找头
            continue
        _, length = _HEADER.unpack_from(buf, pos)  # kind 已在上面读过，length 是第二个字段
        if length > 8 * 1024 * 1024:
            pos += 1  # 长度荒谬视为错位
            continue
        end = pos + 5 + length
        if end > n:
            break  # 半帧：留给下一次
        frames.append((kind, buf[pos + 5:end]))
        pos = end
    return frames, buf[pos:]


def is_frame_stream(first_byte: int) -> bool:
    """首字节嗅探：帧流（0x00/0x01/0x02）→ True；裸 MP3（0xFF sync / 0x49 ID3）→ False"""
    return first_byte in (KIND_END, KIND_AUDIO, KIND_ERROR)


def clamp_speech_rate(v: int) -> int:
    """语速 int [-50,100]（100=2.0x，火山 v3 unidirectional 语义；与 RTC float 倍率不同）"""
    try:
        v = int(v)
    except (TypeError, ValueError):
        return 0
    return max(-50, min(100, v))
