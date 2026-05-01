import streamlit as st
import cv2
import numpy as np
import tempfile
import os
import sys
from PIL import Image
from streamlit_drawable_canvas import st_canvas

# ==================== 核心修复：强制清理并导入标准库subprocess ====================
if 'subprocess' in sys.modules:
    del sys.modules['subprocess']
import subprocess

# ==========================================================================================================

# 页面配置（宽屏布局）
st.set_page_config(page_title="视频去水印工具", layout="wide")

# 自定义CSS美化样式
st.markdown("""
    <style>
    /* 全局样式 */
    .main {
        padding-top: 1rem;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    /* 标题样式 */
    h1 {
        color: #2E86AB;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    h2, h3, h4 {
        color: #3A98B9;
        font-weight: 600;
    }

    /* 按钮样式 */
    .stButton>button {
        background-color: #2E86AB;
        color: white;
        border-radius: 8px;
        height: 2.8rem;
        font-size: 1rem;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stButton>button:hover {
        background-color: #3A98B9;
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }

    /* 下载按钮特殊样式 */
    [data-testid="stDownloadButton"]>button {
        background-color: #16A34A;
        width: 100%;
    }
    [data-testid="stDownloadButton"]>button:hover {
        background-color: #15803d;
    }

    /* 卡片样式 */
    .info-card {
        background-color: #F8FAFC;
        border-radius: 10px;
        padding: 1rem;
        border-left: 4px solid #2E86AB;
        margin-bottom: 1rem;
    }

    /* 进度条样式 */
    .stProgress>div>div {
        background-color: #3A98B9;
    }

    /* 容器样式 */
    .content-container {
        background-color: white;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        height: 100%;
    }

    /* 输入框/选择器样式 */
    .stNumberInput, .stRadio, .stCheckbox {
        padding: 0.5rem 0;
    }

    /* 提示文本样式 */
    .stInfo, .stSuccess, .stError, .stWarning {
        border-radius: 8px;
        padding: 1rem;
    }

    </style>
""", unsafe_allow_html=True)

# ==================== 配置FFmpeg路径 ====================
FFMPEG_EXE_PATH = os.path.normpath(r"D:\installed\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe")


# ==================================================================================

# 检查FFmpeg + subprocess可用性
def check_env():
    if not os.path.exists(FFMPEG_EXE_PATH):
        st.error(f"❌ 未找到ffmpeg.exe！")
        st.info(f"当前路径：{FFMPEG_EXE_PATH}")
        st.markdown("### 请检查：")
        st.markdown("1. 路径是否正确")
        return False

    try:
        test_process = subprocess.Popen(
            [FFMPEG_EXE_PATH, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False
        )
        test_process.communicate(timeout=10)
        if test_process.returncode != 0:
            st.error("❌ FFmpeg可执行文件损坏")
            return False
    except Exception as e:
        st.error(f"❌ 环境异常：{str(e)}")
        return False
    return True


# 缓存视频帧读取
@st.cache_data(ttl=3600)
def get_video_frame(video_path, frame_number):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number - 1)
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None


# 生成去水印预览效果
def generate_preview(frame, x1, y1, x2, y2, mode):
    preview_frame = frame.copy()
    roi = preview_frame[y1:y2, x1:x2]

    if mode == "高斯模糊":
        roi = cv2.GaussianBlur(roi, (51, 51), 0)
    else:
        roi = cv2.resize(roi, (16, 16))
        roi = cv2.resize(roi, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)

    preview_frame[y1:y2, x1:x2] = roi
    return preview_frame


# 封装FFmpeg执行函数
def run_ffmpeg_cmd(cmd, desc):
    status_text = st.empty()
    status_text.info(f"🔄 {desc}...")
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise Exception(f"FFmpeg执行失败，错误日志：\n{stderr}")
        return True
    except Exception as e:
        st.error(f"❌ {desc}失败：{str(e)}")
        return False


# ==================== 主程序 ====================
st.title("🎬 视频去水印工具（模糊/马赛克）")
st.markdown("支持格式：MP4 / MOV / AVI / MKV | 输出视频保留完整原声")

if not check_env():
    st.stop()

# 上传视频
video_file = st.file_uploader("上传视频", type=["mp4", "mov", "avi", "mkv"])

if video_file:
    # ============================================================
    # 🔧 修改点1：检测视频变更，强制重置状态
    # ============================================================
    # 使用文件名作为视频唯一标识
    current_video_id = video_file.name

    # 初始化 session state 相关变量
    if "last_video_id" not in st.session_state:
        st.session_state.last_video_id = None
    if "canvas_key_suffix" not in st.session_state:
        st.session_state.canvas_key_suffix = 0

    # 如果检测到视频换了，清空旧的坐标并更新Canvas Key
    if st.session_state.last_video_id != current_video_id:
        st.session_state.rect_coords = {"left": 50, "top": 50, "width": 200, "height": 100}
        st.session_state.last_video_id = current_video_id
        st.session_state.canvas_key_suffix += 1  # 改变Key强制Streamlit重建组件

    # 保存临时源文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tfile:
        tfile.write(video_file.read())
        video_path = tfile.name

    # 获取视频信息
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    orig_w, orig_h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    fps = 25.0 if fps <= 0 else fps

    # 显示视频信息
    col1, col2, col3 = st.columns(3)
    col1.success(f"尺寸：{orig_w}×{orig_h}")
    col2.success(f"FPS：{fps:.1f}")
    col3.success(f"总帧数：{total_frames}")

    st.subheader("📌 水印区域选择与效果预览")

    # 操作面板
    col_control = st.sidebar.columns([1])[0]
    with col_control:
        frame_number = st.number_input(
            "选择视频帧", min_value=1, max_value=total_frames, value=1, step=10,
            help="切换帧以定位水印位置"
        )
        mode = st.radio("处理模式", ["高斯模糊", "马赛克"], horizontal=False)
        show_preview = True
        if st.button('预览'):
            st.rerun()

        st.markdown("---")
        process_btn = st.button("▶️ 开始去水印", type="primary", width="stretch")

    st.markdown("### 🖼️ 效果预览与区域选择")
    col_canvas, col_preview = st.columns([1.8, 1], gap="large")

    valid_rect = False
    x1, y1, x2, y2 = 0, 0, 0, 0
    preview_available = False
    preview_frame = None

    frame = get_video_frame(video_path, frame_number)
    if frame is None:
        st.error("无法读取该帧，请尝试其他帧号")
    else:
        # ============================================================
        # 🔧 修改点2：自适应画布尺寸 (兼容 1:1 / 16:9 / 9:16)
        # ============================================================
        aspect_ratio = orig_w / orig_h
        max_canvas_size = 700  # 画布单边最大像素限制

        if aspect_ratio >= 1:
            # 横屏或正方形
            display_w = min(orig_w, max_canvas_size)
            display_h = int(display_w / aspect_ratio)
        else:
            # 竖屏
            display_h = min(orig_h, max_canvas_size)
            display_w = int(display_h * aspect_ratio)

        scale = orig_w / display_w  # 坐标缩放比例

        # 调整帧大小用于画布背景
        display_frame = cv2.resize(frame, (display_w, display_h), interpolation=cv2.INTER_AREA)
        pil_frame = Image.fromarray(cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB))

        # ========== 右侧：效果展示区 ==========
        with col_preview:
            st.markdown("### 🎯 去水印效果预览")
            if show_preview:
                if "rect_coords" in st.session_state:
                    rect = st.session_state.rect_coords
                    left, top, width, height = rect["left"], rect["top"], rect["width"], rect["height"]

                    x1, y1 = int(left * scale), int(top * scale)
                    x2, y2 = int((left + width) * scale), int((top + height) * scale)

                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(x2, orig_w), min(y2, orig_h)
                    valid_rect = x2 > x1 and y2 > y1

                    if valid_rect:
                        preview_frame = generate_preview(frame, x1, y1, x2, y2, mode)
                        preview_display = cv2.resize(preview_frame, (display_w, display_h),
                                                     interpolation=cv2.INTER_AREA)
                        st.image(
                            cv2.cvtColor(preview_display, cv2.COLOR_BGR2RGB),
                            caption=f"处理模式：{mode}",
                            width="stretch"
                        )
                        preview_available = True
                    else:
                        st.info("👆 请先在左侧框选水印区域")
                        st.image(pil_frame, caption="原始视频帧", width="stretch")
                else:
                    st.info("👆 请先在左侧框选水印区域")
                    st.image(pil_frame, caption="原始视频帧", width="stretch")
            else:
                st.image(pil_frame, caption="原始视频帧", width="stretch")

        # ========== 左侧：水印区域选择区 ==========
        with col_canvas:
            st.markdown("### ✏️ 区域选择")

            # ============================================================
            # 🔧 修改点3：使用动态 Key 确保画布重建
            # ============================================================
            dynamic_key = f"canvas_{st.session_state.canvas_key_suffix}"

            # 创建可绘制画布
            canvas_result = st_canvas(
                fill_color="rgba(255, 165, 0, 0.1)",
                stroke_width=2,
                stroke_color="#FF0000",
                background_image=pil_frame,
                update_streamlit=True,
                height=display_h,
                width=display_w,
                drawing_mode="rect",
                key=dynamic_key,  # 这里使用动态Key
                initial_drawing={
                    "version": "4.4.0",
                    "objects": [{
                        "type": "rect",
                        "left": st.session_state.rect_coords["left"],
                        "top": st.session_state.rect_coords["top"],
                        "width": st.session_state.rect_coords["width"],
                        "height": st.session_state.rect_coords["height"],
                        "fill": "rgba(255, 165, 0, 0.1)",
                        "stroke": "#FF0000",
                        "strokeWidth": 2,
                    }]
                }
            )

            if canvas_result.json_data and len(canvas_result.json_data["objects"]) > 0:
                rect = canvas_result.json_data["objects"][-1]
                left, top, width, height = rect["left"], rect["top"], rect["width"], rect["height"]

                st.session_state.rect_coords = {"left": left, "top": top, "width": width, "height": height}

                x1, y1 = int(left * scale), int(top * scale)
                x2, y2 = int((left + width) * scale), int((top + height) * scale)

                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(x2, orig_w), min(y2, orig_h)
                valid_rect = x2 > x1 and y2 > y1

                st.success(f"✅ 已选择区域：({x1}, {y1}) 到 ({x2}, {y2})")
            else:
                st.info("👆 请在上方图片上拖动鼠标绘制水印区域")
                valid_rect = False

    if process_btn:
        if not valid_rect:
            st.error("请先绘制水印区域！")
        else:
            temp_files = []
            video_only = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
            audio_only = tempfile.NamedTemporaryFile(delete=False, suffix=".aac").name
            final_output = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
            temp_files.extend([video_path, video_only, audio_only, final_output])

            progress_bar = st.progress(0.0)
            status_text = st.empty()
            process_success = False

            try:
                status_text.info("🔄 正在处理视频画面...")
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(video_only, fourcc, fps, (orig_w, orig_h))
                cap = cv2.VideoCapture(video_path)
                frame_count = 0

                if not cap.isOpened():
                    raise Exception("无法打开源视频文件")
                if not out.isOpened():
                    raise Exception("无法创建视频输出文件")

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret: break

                    roi = frame[y1:y2, x1:x2]
                    if mode == "高斯模糊":
                        roi = cv2.GaussianBlur(roi, (51, 51), 0)
                    else:
                        roi = cv2.resize(roi, (16, 16))
                        roi = cv2.resize(roi, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
                    frame[y1:y2, x1:x2] = roi
                    out.write(frame)

                    frame_count += 1
                    progress = frame_count / total_frames
                    progress_bar.progress(progress)
                    status_text.info(f"🔄 处理中... {frame_count}/{total_frames} 帧 ({progress:.1%})")

                cap.release()
                out.release()

                if not run_ffmpeg_cmd(
                        [FFMPEG_EXE_PATH, "-i", video_path, "-vn", "-acodec", "copy", "-y", audio_only],
                        "正在提取原视频音频"
                ):
                    raise Exception("音频提取失败")

                if not run_ffmpeg_cmd(
                        [FFMPEG_EXE_PATH, "-i", video_only, "-i", audio_only, "-c:v", "copy", "-c:a", "aac", "-strict",
                         "experimental", "-y", final_output],
                        "正在合并音视频"
                ):
                    raise Exception("音视频合并失败")

                progress_bar.progress(1.0)
                status_text.success("✅ 处理完成！视频已保留完整原声")
                process_success = True

                st.markdown("---")
                with open(final_output, "rb") as f:
                    st.download_button(
                        "💾 下载处理后视频",
                        f,
                        file_name="no_watermark.mp4",
                        mime="video/mp4",
                        width="stretch"
                    )

            except Exception as e:
                st.error(f"处理出错：{str(e)}")
            finally:
                for f in temp_files:
                    try:
                        if os.path.exists(f):
                            os.unlink(f)
                    except:
                        pass