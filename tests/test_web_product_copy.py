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

    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    pages_url = "https://joyceleo326.github.io/translation-tech-agent-gui/"
    assert f'<link rel="canonical" href="{pages_url}" />' in page
    assert f'<meta property="og:url" content="{pages_url}" />' in page


def test_web_page_offers_a_complete_review_decision_journey() -> None:
    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert 'data-review-workbench' in page
    assert 'data-source-input' in page
    assert page.count('data-candidate=') == 3
    assert 'data-confirm-candidate' in page
    assert 'data-download-result' in page
    assert 'data-feedback-form' in page
    assert 'data-history-list' in page

    assert '浏览器练习样本' in page
    assert '不会上传文件或调用在线模型' in page
    assert 'localStorage' in script
    assert 'Blob' in script
    assert 'download' in script


def test_web_page_has_no_required_third_party_runtime() -> None:
    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert 'unpkg.com' not in page
    assert 'cdn.' not in page


def test_public_web_identity_is_joyce_only() -> None:
    public_copy = "\n".join(
        [
            (ROOT / "web" / "index.html").read_text(encoding="utf-8"),
            (ROOT / "web" / "README.md").read_text(encoding="utf-8"),
        ]
    )
    assert "Joyce" in public_copy
    disallowed = "Jer" + "ry"
    assert disallowed not in public_copy


def test_browser_verifier_replays_review_at_both_viewports() -> None:
    verifier = (ROOT / "scripts" / "verify_web_demo.cjs").read_text(encoding="utf-8")
    assert '[data-confirm-candidate]' in verifier
    assert '[data-download-result]' in verifier
    assert '[data-feedback-form]' in verifier
    assert '{ width: 1440, height: 1000 }' in verifier
    assert '{ width: 390, height: 844 }' in verifier
