"""
测试运行脚本
提供便捷的测试运行命令
"""
import subprocess
import sys
from pathlib import Path


def run_all_tests():
    """运行所有测试"""
    print("🧪 运行所有测试...")
    result = subprocess.run(
        ["pytest", "tests/", "-v", "--tb=short"],
        cwd=Path(__file__).parent
    )
    return result.returncode


def run_unit_tests():
    """仅运行单元测试"""
    print("🔬 运行单元测试...")
    result = subprocess.run(
        ["pytest", "tests/unit/", "-v", "-m", "unit"],
        cwd=Path(__file__).parent
    )
    return result.returncode


def run_integration_tests():
    """仅运行集成测试"""
    print("🔗 运行集成测试...")
    result = subprocess.run(
        ["pytest", "tests/integration/", "-v", "-m", "integration"],
        cwd=Path(__file__).parent
    )
    return result.returncode


def run_with_coverage():
    """运行测试并生成覆盖率报告"""
    print("📊 运行测试并生成覆盖率报告...")
    result = subprocess.run(
        [
            "pytest",
            "tests/",
            "--cov=src/backend",
            "--cov-report=html",
            "--cov-report=term-missing",
            "-v"
        ],
        cwd=Path(__file__).parent
    )
    if result.returncode == 0:
        print("\n✅ 覆盖率报告已生成在 htmlcov/index.html")
    return result.returncode


def run_specific_test(test_path):
    """运行特定的测试文件或测试"""
    print(f"🎯 运行测试: {test_path}")
    result = subprocess.run(
        ["pytest", test_path, "-v"],
        cwd=Path(__file__).parent
    )
    return result.returncode


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "all":
            sys.exit(run_all_tests())
        elif command == "unit":
            sys.exit(run_unit_tests())
        elif command == "integration":
            sys.exit(run_integration_tests())
        elif command == "coverage":
            sys.exit(run_with_coverage())
        elif command.startswith("tests/"):
            sys.exit(run_specific_test(command))
        else:
            print(f"❌ 未知命令: {command}")
            print("\n可用命令:")
            print("  all          - 运行所有测试")
            print("  unit         - 仅运行单元测试")
            print("  integration  - 仅运行集成测试")
            print("  coverage     - 运行测试并生成覆盖率报告")
            print("  tests/...    - 运行特定测试文件")
            sys.exit(1)
    else:
        # 默认运行所有测试
        sys.exit(run_all_tests())
