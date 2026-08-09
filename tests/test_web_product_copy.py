from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_page_uses_product_task_language() -> None:
    public_copy = "\n".join(
        [
            (ROOT / "web" / "index.html").read_text(encoding="utf-8"),
            (ROOT / "web" / "app.js").read_text(encoding="utf-8"),
        ]
    )

    banned_phrases = (
        "离线即可演示完整生产链",
        "观看完整演示",
        "播放完整功能演示",
        "无 Token 时可完整演示",
        "离线演示，或连接自己的模型开始在线处理",
        "连接自己的 API，让离线演示切换为真实在线处理",
    )

    for phrase in banned_phrases:
        assert phrase not in public_copy

    assert "Yishu-v1.4.1-windows-x64.zip" in public_copy
    assert "/releases/tag/v1.4.1" in public_copy


def test_readme_offers_primary_and_backup_display_entries() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "https://yishu-translation-studio.vercel.app" in readme
    assert "https://joyceleo326.github.io/translation-tech-agent-gui/" in readme
