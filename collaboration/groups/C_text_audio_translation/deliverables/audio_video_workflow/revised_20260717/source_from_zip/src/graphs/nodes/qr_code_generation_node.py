"""
二维码生成节点 - 为整段合成音频生成可扫描的二维码
"""
import os
import logging
from io import BytesIO
import uuid
import urllib.parse
import qrcode
import qrcode.image.pil
from PIL import Image
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import S3SyncStorage
from graphs.state import QRCodeGenerationInput, QRCodeGenerationOutput


logger = logging.getLogger(__name__)


# QR码内容策略说明
# 历史方案: 播放页URL + ?audio=<encoded_url> (要求播放页域名必须存在)
# 当前方案: 直接使用audio URL,扫码后浏览器/微信内嵌播放器直接打开音频
# 优势: 不依赖任何第三方播放页,简单可靠,微信扫码即可播放


def _generate_qr_code_png(content: str) -> bytes:
    """
    生成二维码PNG图片的字节流
    关键参数说明:
    - box_size=10: 标准模块尺寸,手机相机最佳识别粒度
    - error_correction=0(L级,7%纠错): 容量最大化
    - border=4: QR码标准要求的quiet zone(4模块)
    - 额外60px白色padding: 解决微信等手机扫码APP因白边过窄而识别失败的问题
    """
    qr = qrcode.QRCode(
        version=None,  # 自动选择版本
        error_correction=0,  # ERROR_CORRECT_L(7%恢复,容量最大)
        box_size=10,  # 标准模块尺寸
        border=4,  # 4模块边框(QR码国际标准)
    )
    qr.add_data(content)
    qr.make(fit=True)
    # 关键:必须显式转RGB,避免mode=1位图
    img = qr.make_image(fill_color="black", back_color="white", image_factory=qrcode.image.pil.PilImage)
    img = img.convert('RGB')

    # 关键:加额外白色padding(60px),解决微信/部分手机扫码APP因白边不足而无法识别的问题
    # QR码标准要求quiet zone,部分扫码APP需要更宽的白边才能稳定识别
    extra_padding = 60
    new_size = (img.size[0] + 2 * extra_padding, img.size[1] + 2 * extra_padding)
    padded_img = Image.new('RGB', new_size, 'white')
    padded_img.paste(img, (extra_padding, extra_padding))

    buf = BytesIO()
    padded_img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _build_qr_content(audio_url: str) -> str:
    """
    构造QR码内容: 直接使用audio URL
    微信扫码后会直接打开音频文件,浏览器/微信内嵌播放器自动播放
    """
    return audio_url


def qr_code_generation_node(
    state: QRCodeGenerationInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> QRCodeGenerationOutput:
    """
    title: 生成二维码
    desc: 为合成音频生成可扫描的二维码图片,内容为播放页URL携带单条完整音频地址
    integrations: 对象存储
    """
    ctx = runtime.context

    # 1. 校验输入
    tts_audio_urls = state.tts_audio_urls or []
    final_media_url = state.final_media_url
    expected_count = state.expected_audio_count

    logger.info(f"=" * 70)
    logger.info(f"【二维码生成启动】")
    logger.info(f"  tts_audio_urls数组长度: {len(tts_audio_urls)}")
    logger.info(f"  期望音频数量(Excel行数): {expected_count}")
    logger.info(f"  final_media_url: {final_media_url}")
    logger.info(f"  QR码内容策略: 直接使用audio URL(不嵌套播放页)")
    logger.info(f"=" * 70)

    # 2. 数量校验
    # 合并模式: tts_audio_urls 只有1个URL(批量合并为一段完整音频),跳过严格相等校验
    if expected_count > 0 and len(tts_audio_urls) != expected_count:
        if len(tts_audio_urls) == 1 and expected_count > 1:
            logger.info(
                f"检测到合并TTS模式: 1段完整音频对应{expected_count}句人工审核文本"
            )
        else:
            error_msg = (
                f"二维码生成失败: tts_audio_urls数量({len(tts_audio_urls)}) "
                f"与Excel人工审核列行数({expected_count})不一致"
            )
            logger.error(error_msg)
            raise Exception(error_msg)

    # 3. 选择二维码内容
    # 优先使用final_media_url(混音后的完整音视频),这是用户最终想要的播放地址
    # 如果没有final_media_url,则使用tts_audio_urls[0]
    qr_target_url: str = ""
    if final_media_url and final_media_url.strip():
        qr_target_url = final_media_url.strip()
        logger.info(f"使用final_media_url作为二维码目标: {qr_target_url[:80]}...")
    elif tts_audio_urls:
        qr_target_url = tts_audio_urls[0].strip()
        logger.info(f"使用tts_audio_urls[0]作为二维码目标: {qr_target_url[:80]}...")
    else:
        raise Exception("二维码生成失败: 没有可用的音频URL(final_media_url和tts_audio_urls都为空)")

    # 4. 构造QR码内容(直接使用audio URL,微信扫码即可播放)
    qr_content = _build_qr_content(qr_target_url)
    logger.info(f"二维码内容(完整URL): {qr_content}")
    logger.info(f"二维码内容长度: {len(qr_content)} 字符")

    # 5. 生成二维码PNG
    try:
        png_bytes = _generate_qr_code_png(qr_content)
        logger.info(f"二维码PNG生成成功,大小: {len(png_bytes)} bytes")
    except Exception as e:
        logger.error(f"二维码生成失败: {str(e)}")
        raise Exception(f"二维码生成失败: {str(e)}")

    # 6. 上传到对象存储
    file_name = f"qr_code_image_{uuid.uuid4().hex[:8]}.png"
    local_path = f"/tmp/{file_name}"
    try:
        with open(local_path, "wb") as f:
            f.write(png_bytes)
        logger.info(f"二维码已保存到本地: {local_path}")

        # 上传到对象存储
        storage = S3SyncStorage()
        result = storage.upload_file(
            file_content=png_bytes,
            file_name=file_name,
            content_type="image/png"
        )
        key = result if isinstance(result, str) else result.get("key", "")
        logger.info(f"二维码已上传到对象存储, key: {key}")

        # 生成预签名URL(24小时有效)
        qr_code_url = storage.generate_presigned_url(key=key, expire_time=86400)
        logger.info(f"二维码URL: {qr_code_url}")
    except Exception as e:
        logger.error(f"二维码上传失败: {str(e)}")
        raise Exception(f"二维码上传失败: {str(e)}")
    finally:
        # 清理本地临时文件
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except Exception:
            pass

    # 7. 输出结果
    logger.info(f"=" * 70)
    logger.info(f"【二维码生成完成】")
    logger.info(f"  qr_code_url: {qr_code_url}")
    logger.info(f"  包含音频数: 1 (合并后的完整音频)")
    logger.info(f"  对应原Excel行数: {expected_count}")
    logger.info(f"  二维码内容: {qr_content}")
    logger.info(f"=" * 70)

    return QRCodeGenerationOutput(
        qr_code_url=qr_code_url,
        qr_content=qr_content,
        audio_list_count=len(tts_audio_urls),
        expected_audio_count=expected_count
    )
