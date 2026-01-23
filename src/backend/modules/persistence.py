"""
持久化模块
负责会话数据的保存和加载
"""
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from ..core.schema import SessionData
from ..config_loader import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SessionManager:
    """
    会话管理器
    负责会话的持久化存储和恢复
    """

    def __init__(self):
        """初始化会话管理器"""
        self.settings = get_settings()
        self.sessions_dir = Path(self.settings.storage.sessions_dir)
        self.sessions_dir = Path(self.settings.storage.sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.active_session: Optional[SessionData] = None

    def set_active_session(self, session: SessionData):
        """设置当前活跃的会话（内存中）"""
        self.active_session = session

    def get_active_session(self) -> Optional[SessionData]:
        """获取当前活跃的会话"""
        return self.active_session

    def clear_active_session(self):
        """清除活跃会话"""
        self.active_session = None

    async def save_session(self, session: SessionData) -> bool:
        """
        保存会话数据

        Args:
            session: 会话数据

        Returns:
            bool: 是否保存成功
        """
        try:
            file_path = self.sessions_dir / f"{session.session_id}.json"
            temp_path = file_path.with_suffix(".tmp")

            # 序列化会话数据
            session_json = session.model_dump_json(indent=2, ensure_ascii=False)

            # 原子写入：先写临时文件，再重命名
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(session_json)

            # 原子操作重命名
            temp_path.replace(file_path)

            logger.info(f"会话 {session.session_id} 已保存")
            return True

        except Exception as e:
            logger.error(f"保存会话失败: {e}")
            return False

    async def load_session(self, session_id: str) -> Optional[SessionData]:
        """
        加载会话数据

        Args:
            session_id: 会话 ID

        Returns:
            Optional[SessionData]: 会话数据，如果不存在则返回 None
        """
        try:
            file_path = self.sessions_dir / f"{session_id}.json"

            if not file_path.exists():
                logger.warning(f"会话文件不存在: {file_path}")
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                session_json = f.read()

            # 反序列化
            session_data = json.loads(session_json)
            session = SessionData(**session_data)

            logger.info(f"会话 {session_id} 已加载")
            return session

        except json.JSONDecodeError as e:
            logger.error(f"会话文件格式错误: {e}")
            return None
        except Exception as e:
            logger.error(f"加载会话失败: {e}")
            return None

    async def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话 ID

        Returns:
            bool: 是否删除成功
        """
        try:
            file_path = self.sessions_dir / f"{session_id}.json"

            if file_path.exists():
                file_path.unlink()
                logger.info(f"会话 {session_id} 已删除")
                return True
            else:
                logger.warning(f"会话文件不存在: {file_path}")
                return False

        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return False

    def list_sessions(self) -> List[Dict]:
        """
        列出所有会话

        Returns:
            List[Dict]: 会话信息列表
        """
        sessions = []

        try:
            for file_path in self.sessions_dir.glob("*.json"):
                # 排除报告文件
                if file_path.name.endswith("_report.json"):
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)

                    # 提取基本信息
                    session_info = {
                        "session_id": session_data.get("session_id"),
                        "global_goal": session_data.get("global_goal"),
                        "created_at": session_data.get("created_at"),
                        "updated_at": session_data.get("updated_at"),
                        "status": session_data.get("status"),
                        "total_simulations": session_data.get("total_simulations", 0),
                        "total_nodes": len(session_data.get("nodes", {})),
                        "total_facts": len(session_data.get("global_facts", [])),
                        "file_size": file_path.stat().st_size
                    }
                    sessions.append(session_info)

                except Exception as e:
                    logger.error(f"读取会话文件失败 {file_path}: {e}")
                    continue

            # 按更新时间排序
            sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        except Exception as e:
            logger.error(f"列出会话失败: {e}")

        return sessions

    async def backup_session(self, session_id: str, backup_dir: str) -> bool:
        """
        备份会话到指定目录

        Args:
            session_id: 会话 ID
            backup_dir: 备份目录

        Returns:
            bool: 是否备份成功
        """
        try:
            src_path = self.sessions_dir / f"{session_id}.json"
            dst_path = Path(backup_dir) / f"{session_id}_backup.json"

            if not src_path.exists():
                logger.warning(f"源会话文件不存在: {src_path}")
                return False

            # 创建备份目录
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # 复制文件
            shutil.copy2(src_path, dst_path)
            logger.info(f"会话 {session_id} 已备份到 {dst_path}")
            return True

        except Exception as e:
            logger.error(f"备份会话失败: {e}")
            return False

    def get_session_count(self) -> int:
        """
        获取会话总数

        Returns:
            int: 会话总数
        """
        try:
            return len(list(self.sessions_dir.glob("*.json")))
        except Exception:
            return 0

    def cleanup_old_sessions(self, days: int = 30) -> int:
        """
        清理旧会话

        Args:
            days: 保留天数

        Returns:
            int: 清理的会话数量
        """
        import time

        cleaned_count = 0
        cutoff_time = time.time() - (days * 24 * 60 * 60)

        try:
            for file_path in self.sessions_dir.glob("*.json"):
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    cleaned_count += 1
                    logger.info(f"已清理旧会话: {file_path}")

        except Exception as e:
            logger.error(f"清理旧会话失败: {e}")

        return cleaned_count

    async def save_report(self, session_id: str, report_data: Dict) -> bool:
        """保存会话报告（合并到会话文件中）"""
        try:
            # 加载会话
            session = await self.load_session(session_id)
            if not session:
                logger.error(f"保存报告失败：会话 {session_id} 不存在")
                return False

            # 更新报告字段
            session.report = report_data
            
            # 保存整个会话
            return await self.save_session(session)
            
        except Exception as e:
            logger.error(f"保存会话报告失败: {e}")
            return False

    async def load_report(self, session_id: str) -> Optional[Dict]:
        """加载会话报告"""
        try:
            # 1. 尝试从会话中加载
            session = await self.load_session(session_id)
            if session and session.report:
                return session.report

            # 2. 兼容旧版本：尝试加载独立的报告文件
            legacy_path = self.sessions_dir / f"{session_id}_report.json"
            if legacy_path.exists():
                logger.info(f"加载旧版报告文件: {legacy_path}")
                with open(legacy_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            return None
        except Exception as e:
            logger.error(f"加载会话报告失败: {e}")
            return None


# 全局会话管理器实例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """
    获取全局会话管理器实例

    Returns:
        SessionManager: 会话管理器实例
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


# 自动保存装饰器
def auto_save(interval: int = 5):
    """
    自动保存装饰器

    Args:
        interval: 保存间隔（步数）
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 执行原函数
            result = await func(*args, **kwargs)

            # 获取会话实例（假设第一个参数是引擎或包含会话的对象）
            if args and hasattr(args[0], 'session'):
                session = args[0].session

                # 检查是否需要保存
                if session.total_simulations % interval == 0:
                    session_manager = get_session_manager()
                    await session_manager.save_session(session)
                    logger.debug(f"自动保存会话 {session.session_id}")

            return result
    return decorator