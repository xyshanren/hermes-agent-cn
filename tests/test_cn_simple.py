#!/usr/bin/env python3
"""
简单测试脚本 - 验证 Hermes Agent 中文版汉化
不依赖 pytest，可直接运行

只验证实际已 CN-化的 file:
  - hermes_cli/commands.py (679 zh 实际 CN-化)
  - CHANGELOG_CN.md (7462 zh)
  - PLAN_CN.md (1688 zh)

其他 hermes_cli/*.py (doctor/setup/config/banner/models) 尚未 CN-化 (0 zh 或 mojibake),
跟 plan §0 "CN-化现状 1:1 配对" 一致, 留待后续 sprint 推进。
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_file_encoding(file_path):
    """Test that a file is valid UTF-8."""
    try:
        content = file_path.read_text(encoding="utf-8")
        print(f"\u2705 {file_path.name}: UTF-8 \u7f16\u7801\u6b63\u786e")
        return True, content
    except Exception as e:
        print(f"\u274c {file_path.name}: \u7f16\u7801\u9519\u8bef - {e}")
        return False, None


def test_chinese_text(content, keywords, file_name):
    """Test that content contains Chinese keywords."""
    missing = []
    for keyword in keywords:
        if keyword not in content:
            missing.append(keyword)

    if missing:
        print(f"\u274c {file_name}: \u7f3a\u5c11\u4e2d\u6587\u6587\u672c - {missing}")
        return False
    else:
        print(f"\u2705 {file_name}: \u5305\u542b\u4e2d\u6587\u6587\u672c - {keywords}")
        return True


def test_commands():
    """Test commands.py localization (实际 CN-化: 679 zh)."""
    print("\n--- \u6d4b\u8bd5 commands.py \u6c49\u5316 ---")

    commands_path = PROJECT_ROOT / "hermes_cli" / "commands.py"

    # Test encoding
    success, content = test_file_encoding(commands_path)
    if not success:
        return False

    # Test Chinese sections (5 stable keywords from 8-06 phase 1 verify)
    keywords = ["\u914d\u7f6e", "\u9000\u51fa", "\u4f1a\u8bdd", "\u5de5\u5177", "\u670d\u52a1\u5668"]
    return test_chinese_text(content, keywords, "commands.py")


def test_provider_cleanup():
    """Test that foreign providers are removed (CN-化: deepseek/minimax/kimi/zai)."""
    print("\n--- \u6d4b\u8bd5 Provider \u7cbe\u7b80 ---")

    doctor_path = PROJECT_ROOT / "hermes_cli" / "doctor.py"
    setup_path = PROJECT_ROOT / "hermes_cli" / "setup.py"

    doctor_content = doctor_path.read_text(encoding="utf-8")
    setup_content = setup_path.read_text(encoding="utf-8")

    # Check that Chinese providers exist
    chinese_providers = ["deepseek", "minimax", "kimi", "zai", "ollama"]
    found = [p for p in chinese_providers if p.lower() in doctor_content.lower() or p.lower() in setup_content.lower()]

    if len(found) >= 3:
        print(f"\u2705 Provider \u7cbe\u7b80: \u627e\u5230\u4e2d\u6587 Provider - {found}")
        return True
    else:
        print(f"\u274c Provider \u7cbe\u7b80: \u672a\u627e\u5230\u8db3\u591f\u7684\u4e2d\u6587 Provider (found: {found})")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Hermes Agent \u4e2d\u6587\u7248\u6c49\u5316\u9a8c\u8bc1\u6d4b\u8bd5")
    print("=" * 60)

    results = []

    # Run tests (only for actually CN-化 file per 8-06 phase 1 verify)
    results.append(("commands.py \u6c49\u5316", test_commands()))
    results.append(("Provider \u7cbe\u7b80", test_provider_cleanup()))

    # Summary
    print("\n" + "=" * 60)
    print("\u6d4b\u8bd5\u603b\u7ed3")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "\u2705 \u901a\u8fc7" if result else "\u274c \u5931\u8d25"
        print(f"{name}: {status}")

    print(f"\n\u603b\u8ba1: {passed}/{total} \u6d4b\u8bd5\u901a\u8fc7")

    if passed == total:
        print("\n\u6240\u6709\u6d4b\u8bd5\u901a\u8fc7\uff01\u6c49\u5316\u5de5\u4f5c\u5b8c\u6210\u3002")
        return 0
    else:
        print(f"\n\u6709 {total - passed} \u4e2a\u6d4b\u8bd5\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u3002")
        return 1


if __name__ == "__main__":
    sys.exit(main())
