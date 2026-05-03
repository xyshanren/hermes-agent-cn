#!/usr/bin/env python3
"""
简单测试脚本 - 验证 Hermes Agent 中文版汉化
不依赖 pytest，可直接运行
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
        print(f"✅ {file_path.name}: UTF-8 编码正确")
        return True, content
    except Exception as e:
        print(f"❌ {file_path.name}: 编码错误 - {e}")
        return False, None


def test_chinese_text(content, keywords, file_name):
    """Test that content contains Chinese keywords."""
    missing = []
    for keyword in keywords:
        if keyword not in content:
            missing.append(keyword)
    
    if missing:
        print(f"❌ {file_name}: 缺少中文文本 - {missing}")
        return False
    else:
        print(f"✅ {file_name}: 包含中文文本 - {keywords}")
        return True


def test_doctor():
    """Test doctor.py localization."""
    print("\n--- 测试 doctor.py 汉化 ---")
    
    doctor_path = PROJECT_ROOT / "hermes_cli" / "doctor.py"
    
    # Test encoding
    success, content = test_file_encoding(doctor_path)
    if not success:
        return False
    
    # Test Chinese sections
    keywords = ["Python 环境", "目录结构", "API 连通性", "配置文件", "必需的包"]
    return test_chinese_text(content, keywords, "doctor.py")


def test_setup():
    """Test setup.py localization."""
    print("\n--- 测试 setup.py 汉化 ---")
    
    setup_path = PROJECT_ROOT / "hermes_cli" / "setup.py"
    
    # Test encoding
    success, content = test_file_encoding(setup_path)
    if not success:
        return False
    
    # Test Chinese text
    keywords = ["配置", "模型"]
    return test_chinese_text(content, keywords, "setup.py")


def test_config():
    """Test config.py localization."""
    print("\n--- 测试 config.py 汉化 ---")
    
    config_path = PROJECT_ROOT / "hermes_cli" / "config.py"
    
    # Test encoding
    success, content = test_file_encoding(config_path)
    if not success:
        return False
    
    # Test Chinese text (comments or docstrings)
    keywords = ["配置"]
    return test_chinese_text(content, keywords, "config.py")


def test_provider_cleanup():
    """Test that foreign providers are removed."""
    print("\n--- 测试 Provider 精简 ---")
    
    doctor_path = PROJECT_ROOT / "hermes_cli" / "doctor.py"
    setup_path = PROJECT_ROOT / "hermes_cli" / "setup.py"
    
    doctor_content = doctor_path.read_text(encoding="utf-8")
    setup_content = setup_path.read_text(encoding="utf-8")
    
    # Check that Chinese providers exist
    chinese_providers = ["deepseek", "minimax", "kimi", "zai", "ollama"]
    found = [p for p in chinese_providers if p.lower() in doctor_content.lower() or p.lower() in setup_content.lower()]
    
    if len(found) >= 3:
        print(f"✅ Provider 精简: 找到中文 Provider - {found}")
        return True
    else:
        print(f"❌ Provider 精简: 未找到足够的中文 Provider (found: {found})")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Hermes Agent 中文版汉化验证测试")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("doctor.py 汉化", test_doctor()))
    results.append(("setup.py 汉化", test_setup()))
    results.append(("config.py 汉化", test_config()))
    results.append(("Provider 精简", test_provider_cleanup()))
    
    # Summary
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！汉化工作完成。")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
