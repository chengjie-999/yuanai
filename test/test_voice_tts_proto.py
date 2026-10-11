# -*- coding: utf-8 -*-
"""TTS 流式帧协议纯函数测试 — pack/iter_frames/clamp（零网络零 LLM）

运行：pytest test/test_voice_tts_proto.py -v
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

from api.v1.voice.tts_proto import (  # noqa: E402
    pack_frame, pack_error, pack_end, iter_frames, is_frame_stream,
    clamp_speech_rate, KIND_AUDIO, KIND_ERROR, KIND_END,
)


def test_pack_iter_roundtrip():
    audio = b"\xff\xfb\x90\x00" * 100
    frames = [pack_frame(KIND_AUDIO, audio), pack_error(500, "合成失败"), pack_end()]
    parsed, rest = iter_frames(b"".join(frames))
    assert rest == b""
    assert parsed[0] == (KIND_AUDIO, audio)
    assert parsed[1][0] == KIND_ERROR
    assert json.loads(parsed[1][1].decode()) == {"code": 500, "message": "合成失败"}
    assert parsed[2] == (KIND_END, b"")


def test_half_frame_across_reads():
    """半帧残留：跨 read 拼接不丢帧"""
    full = pack_frame(KIND_AUDIO, b"abc") + pack_end()
    a, rest = iter_frames(full[:3])      # 只给头部 3 字节
    assert a == [] and rest == full[:3]
    b, rest2 = iter_frames(rest + full[3:])  # 续传
    assert b[0] == (KIND_AUDIO, b"abc") and rest2 == b""


def test_corrupted_byte_resync():
    """字节错位/坏长度 → 滑动一个字节重新同步，不卡死流"""
    garbage = b"\x07\x00\x00" + pack_frame(KIND_END)
    parsed, rest = iter_frames(garbage)
    assert parsed and parsed[0][0] == KIND_END


def test_sniffing():
    assert is_frame_stream(0x00) and is_frame_stream(0x01) and is_frame_stream(0x02)
    assert not is_frame_stream(0xFF)  # MP3 sync
    assert not is_frame_stream(0x49)  # 'I' ID3


def test_clamp_speech_rate():
    assert clamp_speech_rate(0) == 0
    assert clamp_speech_rate(100) == 100  # 2.0x
    assert clamp_speech_rate(-50) == -50
    assert clamp_speech_rate(200) == 100
    assert clamp_speech_rate(-100) == -50
    assert clamp_speech_rate("bad") == 0
    assert clamp_speech_rate(None) == 0
