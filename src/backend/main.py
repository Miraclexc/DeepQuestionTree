"""
DeepQuestionTree 主程序
FastAPI 应用入口
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uuid

from .config_loader import get_settings, reload_settings
from .core.schema import SessionData, Node, QAInteraction
from .core.mcts_engine import MCTSEngine
from .llm.llm_client import OpenAICompatibleClient
from .llm.mock_client import MockClient
from .llm.client_interface import BaseLLMClient
from .modules.questioner import Questioner
from .modules.compressor import Compressor
from .modules.pruner import Pruner
from .modules.integrator import Integrator
from .modules.persistence import get_session_manager, auto_save
from .modules import visualizer_api
from .llm.embedding import get_embedding_manager
from .utils.logger import setup_logging, get_logger, request_id_ctx, session_id_ctx

# 设置日志
setup_logging()
logger = get_logger(__name__)

# 全局状态
current_session: Optional[SessionData] = None
mcts_engine: Optional[MCTSEngine] = None
llm_client: Optional[BaseLLMClient] = None
questioner: Optional[Questioner] = None
compressor: Optional[Compressor] = None
pruner: Optional[Pruner] = None
integrator: Optional[Integrator] = None
mcts_running = False
mcts_task: Optional[asyncio.Task] = None


# API 请求/响应模型
class StartRequest(BaseModel):
    goal: str = Field(..., description="探索目标问题")
    session_id: Optional[str] = Field(None, description="恢复的会话ID（可选）")
    use_mock: Optional[bool] = Field(False, description="是否使用Mock客户端")


class StartResponse(BaseModel):
    session_id: str
    message: str
    status: str


class TreeNode(BaseModel):
    id: str
    type: str = "default"
    position: Dict[str, float]
    data: Dict[str, Any]


class TreeEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str = "default"


class TreeResponse(BaseModel):
    nodes: list[TreeNode]
    edges: list[TreeEdge]
    statistics: Dict[str, Any]


class NodeDetailResponse(BaseModel):
    node: Dict[str, Any]
    path: list[Dict[str, Any]]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("DeepQuestionTree 启动中...")
    yield
    # 关闭时清理
    logger.info("DeepQuestionTree 正在关闭...")
    global mcts_running
    mcts_running = False
    if mcts_task:
        mcts_task.cancel()


# 创建 FastAPI 应用
app = FastAPI(
    title="DeepQuestionTree API",
    description="基于 MCTS 和 LLM 的深度问题探索系统",
    version="1.0.0",
    lifespan=lifespan
)

# 注册路由
app.include_router(visualizer_api.router)

# 添加 CORS 中间件
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"{settings.app.frontend_host}:{settings.app.frontend_port}",
        "http://localhost:3000", # Fallback
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加 Request ID 中间件
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    token = request_id_ctx.set(request_id)
    
    # 尝试从 Header 或全局状态获取 session_id
    if current_session:
        session_token = session_id_ctx.set(current_session.session_id)
    
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_ctx.reset(token)
        if current_session and 'session_token' in locals():
            session_id_ctx.reset(session_token)


def initialize_clients(use_mock: bool = False) -> BaseLLMClient:
    """初始化 LLM 客户端"""
    settings = get_settings()
    if use_mock or settings.app.mock_llm:
        logger.info("使用 Mock LLM 客户端")
        return MockClient()
    else:
        logger.info("使用 OpenAI 兼容 LLM 客户端")
        client = OpenAICompatibleClient()
        # 设置嵌入管理器的客户端
        embedding_manager = get_embedding_manager()
        embedding_manager.set_client(client)
        return client


def initialize_modules():
    """初始化所有模块"""
    global llm_client, questioner, compressor, pruner, integrator
    global embedding_manager

    settings = get_settings()

    # 初始化 LLM 客户端
    llm_client = initialize_clients(settings.app.mock_llm)

    # 初始化嵌入管理器
    embedding_manager = get_embedding_manager()

    # 初始化功能模块
    questioner = Questioner(llm_client, embedding_manager)
    compressor = Compressor(llm_client)
    pruner = Pruner(llm_client, embedding_manager)
    integrator = Integrator(llm_client)


async def single_mcts_worker(worker_id: int):
    """单个 MCTS 工作线程"""
    global mcts_running, mcts_engine, current_session

    logger.info(f"Worker {worker_id} started")
    
    while mcts_running and mcts_engine:
        try:
            # 执行一步 MCTS
            new_node_id = await mcts_engine.run_step()

            if new_node_id:
                logger.debug(f"[Worker {worker_id}] 扩展新节点: {new_node_id}")

            # 检查是否应该停止
            # 注意：多个 worker 可能同时检查，但这没关系，只要有一个触发停止即可
            if mcts_engine.should_stop():
                logger.info(f"[Worker {worker_id}] 检测到停止条件")
                mcts_running = False
                break

            # 自动保存 (仅由 worker 0 处理，避免冲突)
            # 只有在产生新节点（确实进行了模拟Step）时才保存，防止 run_step 返回 None 导致不断重复保存
            if worker_id == 0 and new_node_id and current_session and current_session.total_simulations % 5 == 0:
                session_manager = get_session_manager()
                await session_manager.save_session(current_session)

            # 短暂休眠
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"[Worker {worker_id}] 出错: {e}")
            # 单个 worker 出错不应导致整个任务崩溃，除非是致命错误
            # 简单策略：暂停一下再试
            await asyncio.sleep(1.0)

    logger.info(f"Worker {worker_id} stopped")


async def run_mcts_loop():
    """MCTS 后台主循环 (Supervisor)"""
    global mcts_running, mcts_engine, current_session

    if current_session:
        session_id_ctx.set(current_session.session_id)

    settings = get_settings()
    num_workers = settings.mcts.parallel_workers
    
    logger.info(f"Starting MCTS loop with {num_workers} parallel workers")

    # 创建并运行 workers
    tasks = [
        asyncio.create_task(single_mcts_worker(i))
        for i in range(num_workers)
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("MCTS loop cancelled")
        # 确保所有子任务都被取消
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        # 更新会话状态并保存
        if current_session:
            current_session.status = "completed" if current_session.status == "running" else current_session.status
            try:
                session_manager = get_session_manager()
                await session_manager.save_session(current_session)
                logger.info(f"Session {current_session.session_id} finished with status: {current_session.status}")
            except Exception as e:
                logger.error(f"Error saving session state: {e}")


@app.post("/api/start", response_model=StartResponse)
async def start_session(request: StartRequest, background_tasks: BackgroundTasks):
    """
    启动新的探索会话
    """
    global current_session, mcts_engine, mcts_running, mcts_task
    global llm_client, questioner, compressor, pruner, integrator

    try:
        # 停止当前运行的会话
        if mcts_running:
            mcts_running = False
            if mcts_task:
                mcts_task.cancel()

        # 初始化模块
        initialize_modules()

        # 检查是否恢复已有会话
        session_manager = get_session_manager()
        if request.session_id:
            current_session = await session_manager.load_session(request.session_id)
            if current_session:
                session_manager.set_active_session(current_session)
                logger.info(f"恢复会话: {request.session_id}")
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"会话 {request.session_id} 不存在"
                )
        else:
            # 创建新会话
            current_session = SessionData(
                global_goal=request.goal,
                status="running",
                mcts_config=get_settings().mcts.dict()
            )
            # 创建根节点
            root_node = Node(
                id=current_session.root_node_id,
                depth=0,
                interaction=QAInteraction(
                    question=request.goal,
                    answer="探索起点",
                    summary="用户提出的问题",
                    model_used="System"
                )
            )
            current_session.add_node(root_node)
            
            # 立即保存初始会话状态
            await session_manager.save_session(current_session)
            
            # 设置活跃会话（内存共享）
            session_manager.set_active_session(current_session)
            
            logger.info(f"创建新会话: {current_session.session_id}")

        # 初始化 MCTS 引擎
        mcts_engine = MCTSEngine(
            session=current_session,
            questioner=questioner,
            pruner=pruner,
            compressor=compressor,
            settings=get_settings()
        )

        # 启动 MCTS 循环
        mcts_running = True
        mcts_task = asyncio.create_task(run_mcts_loop())

        return StartResponse(
            session_id=current_session.session_id,
            message="探索已启动",
            status="running"
        )

    except Exception as e:
        logger.error(f"启动会话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/stop")
async def stop_session():
    """
    停止当前探索会话
    """
    global mcts_running, mcts_task, current_session

    try:
        if mcts_running:
            mcts_running = False
            if mcts_task:
                mcts_task.cancel()

            if current_session:
                current_session.status = "paused"
                # 保存会话
                session_manager = get_session_manager()
                await session_manager.save_session(current_session)

            return {"message": "探索已停止"}

        else:
            return {"message": "没有正在运行的探索"}

    except Exception as e:
        logger.error(f"停止会话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/tree", response_model=TreeResponse)
async def get_tree_data():
    """
    获取当前的树结构数据（用于前端可视化）
    """
    global current_session, mcts_engine

    if not current_session:
        return TreeResponse(nodes=[], edges=[], statistics={})

    try:
        # 转换节点数据
        nodes = []
        edges = []

        # 计算布局（简单的层级布局）
        level_nodes = {}  # depth -> [node_ids]

        for node_id, node in current_session.nodes.items():
            # 按深度分组
            if node.depth not in level_nodes:
                level_nodes[node.depth] = []
            level_nodes[node.depth].append(node_id)

        # 生成节点和边
        for depth, node_ids in level_nodes.items():
            for i, node_id in enumerate(node_ids):
                node = current_session.nodes[node_id]

                # 计算位置
                x = i * 200 - (len(node_ids) - 1) * 100
                y = depth * 150

                # 节点数据
                node_data = {
                    "visits": node.state.visit_count,
                    "value": node.state.average_value,
                    "depth": node.depth,
                    "isPruned": node.is_pruned,
                    "isTerminal": node.is_terminal,
                    "question": node.interaction.question if node.interaction else None,
                    "factsCount": len(node.new_facts)
                }

                # 节点样式
                node_type = "default"
                if node.is_pruned:
                    node_type = "pruned"
                elif node.is_terminal:
                    node_type = "terminal"
                elif node.state.visit_count == 0:
                    node_type = "unvisited"

                tree_node = TreeNode(
                    id=node_id,
                    type=node_type,
                    position={"x": x, "y": y},
                    data=node_data
                )
                nodes.append(tree_node)

                # 生成边
                if node.parent_id and node.parent_id in current_session.nodes:
                    edge = TreeEdge(
                        id=f"{node.parent_id}-{node_id}",
                        source=node.parent_id,
                        target=node_id
                    )
                    edges.append(edge)

        # 获取统计信息
        statistics = mcts_engine.get_tree_statistics() if mcts_engine else {}

        return TreeResponse(
            nodes=nodes,
            edges=edges,
            statistics=statistics
        )

    except Exception as e:
        logger.error(f"获取树数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/node/{node_id}", response_model=NodeDetailResponse)
async def get_node_details(node_id: str):
    """
    获取节点的详细信息
    """
    global current_session

    if not current_session or node_id not in current_session.nodes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="节点不存在"
        )

    try:
        node = current_session.nodes[node_id]

        # 节点详细信息
        node_details = {
            "id": node.id,
            "depth": node.depth,
            "visits": node.state.visit_count,
            "value": node.state.average_value,
            "isPruned": node.is_pruned,
            "pruneReason": node.prune_reason,
            "isTerminal": node.is_terminal,
            "interaction": {
                "question": node.interaction.question if node.interaction else None,
                "answer": node.interaction.answer if node.interaction else None,
                "summary": node.interaction.summary if node.interaction else None,
                "tokensUsed": node.interaction.tokens_used if node.interaction else 0,
                "createdAt": node.interaction.created_at.isoformat() if node.interaction else None
            },
            "facts": [
                {
                    "content": fact.content,
                    "confidence": fact.confidence,
                    "createdAt": fact.created_at.isoformat()
                }
                for fact in node.new_facts
            ],
            "createdAt": node.created_at.isoformat(),
            "updatedAt": node.updated_at.isoformat()
        }

        # 获取路径信息
        path = []
        current_id = node_id
        while current_id:
            path_node = current_session.nodes[current_id]
            path.append({
                "id": path_node.id,
                "depth": path_node.depth,
                "question": path_node.interaction.question if path_node.interaction else None,
                "visits": path_node.state.visit_count,
                "value": path_node.state.average_value
            })
            current_id = path_node.parent_id

        path.reverse()  # 从根到当前节点

        return NodeDetailResponse(
            node=node_details,
            path=path
        )

    except Exception as e:
        logger.error(f"获取节点详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/sessions")
async def list_sessions():
    """
    列出所有会话
    """
    try:
        session_manager = get_session_manager()
        sessions = session_manager.list_sessions()
        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"列出会话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/session/{session_id}/load")
async def load_session(session_id: str):
    """
    加载历史会话
    """
    global current_session, mcts_engine, mcts_running

    try:
        # 停止当前运行的会话
        if mcts_running:
            mcts_running = False

        session_manager = get_session_manager()
        loaded_session = await session_manager.load_session(session_id)

        if not loaded_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="会话不存在"
            )

        current_session = loaded_session
        
        # 设置活跃会话
        session_manager.set_active_session(current_session)

        # 创建新的 MCTS 引擎实例（但不运行）
        settings = get_settings()
        llm_client = initialize_clients(settings.app.mock_llm)
        embedding_manager = get_embedding_manager()
        questioner = Questioner(llm_client, embedding_manager)
        compressor = Compressor(llm_client)
        pruner = Pruner(llm_client, embedding_manager)
        integrator = Integrator(llm_client)

        mcts_engine = MCTSEngine(
            session=current_session,
            questioner=questioner,
            compressor=compressor,
            pruner=pruner,
            settings=settings
        )

        return {
            "message": "会话加载成功",
            "session_id": session_id,
            "goal": current_session.goal,
            "status": current_session.status
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"加载会话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/report")
async def get_final_report(session_id: Optional[str] = None):
    """
    获取最终探索报告
    """
    global current_session, integrator

    # 确定目标会话
    target_session = current_session
    if session_id:
        session_manager = get_session_manager()
        # 尝试加载指定会话（这里不改变全局 active session，只是临时加载）
        loaded = await session_manager.load_session(session_id)
        if loaded:
            target_session = loaded

    if not target_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或未指定"
        )
    
    # 如果指定了 session_id 但与当前活跃的不一致，优先使用加载的
    # 如果没指定，就用当前的

    try:
        # 尝试从缓存加载报告
        session_manager = get_session_manager()
        cached_report = await session_manager.load_report(target_session.session_id)
        if cached_report:
            logger.info(f"返回缓存的报告: {target_session.session_id}")
            return cached_report

        if not integrator:
            # 如果仅仅是查看历史，integrator 可能没初始init，但这不应该发生，因为 startup 会 init
            # 但为了安全
            initialize_modules()
            if not integrator:
                 raise Exception("整合模块初始化失败")

        # 生成报告
        report = await integrator.generate_final_report(target_session)
        
        # 保存报告到缓存
        await session_manager.save_report(target_session.session_id, report)

        return report

    except Exception as e:
        logger.error(f"生成报告失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/status")
async def get_status():
    """
    获取系统状态
    """
    global mcts_running, current_session

    status = {
        "mcts_running": mcts_running,
        "has_active_session": current_session is not None,
        "environment": get_settings().app.env
    }

    if current_session:
        status.update({
            "session_id": current_session.session_id,
            "session_status": current_session.status,
            "total_simulations": current_session.total_simulations,
            "tree_depth": current_session.get_tree_depth(),
            "total_nodes": current_session.get_total_nodes()
        })

    return status


@app.post("/api/config/reload")
async def reload_config():
    """
    重新加载配置
    """
    try:
        reload_settings()
        initialize_modules()
        return {"message": "配置已重新加载"}
    except Exception as e:
        logger.error(f"重新加载配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app.api_port,
        reload=settings.app.debug,
        log_level="info"
    )