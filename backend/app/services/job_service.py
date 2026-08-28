"""任务执行服务：校验后的解析结果 → 结果表。"""
import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.crypto import decrypt
from app.core.logging import setup_logging
from app.db.session import get_engine
from app.models.datasource import Datasource, MetaColumn, MetaTable
from app.models.job import Job, ResultTable
from app.models.parse_history import ParseHistory
from app.services import db_service, duckdb_service
from app.services.nl_parser import ParseResult, TableMeta, validate
from app.services.sql_builder import build_select_sql

logger = setup_logging()


def _load_table_meta(db: Session, table_id: int) -> tuple[MetaTable, TableMeta]:
    t = db.get(MetaTable, table_id)
    cols = db.query(MetaColumn).filter(MetaColumn.table_id == t.id).order_by(MetaColumn.column_order).all()
    meta = TableMeta(
        table_name=t.table_name,
        business_name=t.business_name,
        columns=[
            {
                "name": c.column_name,
                "business_name": c.business_name,
                "data_type": c.data_type,
                "role": c.role,
                "default_agg": c.default_agg,
            }
            for c in cols
        ],
    )
    return t, meta


def _execute(job_id: int) -> None:
    """任务主体：在独立会话中执行，任何异常标记任务失败。"""
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        job = db.get(Job, job_id)
        if job is None:
            logger.error("任务不存在: %s", job_id)
            return
        job.status = "running"
        job.started_at = datetime.now(UTC)
        db.commit()
        try:
            _run_job(db, job)
        except Exception as e:
            logger.exception("任务 %s 执行失败", job_id)
            job.status = "failed"
            job.error_msg = str(e)[:2000]
            job.finished_at = datetime.now(UTC)
            db.commit()


def _run_job(db: Session, job: Job) -> None:
    history = db.get(ParseHistory, job.parse_id)
    t, meta = _load_table_meta(db, history.table_id)
    raw = json.loads(history.parse_json)

    result, errors = validate(raw, meta)
    if result is None:
        raise ValueError(f"解析结果校验失败: {'；'.join(errors)}")

    select_sql = build_select_sql(meta, result)
    ds = db.get(Datasource, t.datasource_id)

    # 结果表命名：rpt_/detail_{job_id}_{时间戳}
    prefix = "rpt" if result.intent == "aggregate" else "detail"
    rpt_name = f"{prefix}_{job.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    if ds.type == "excel":
        duckdb_service.execute_ddl(f'DROP TABLE IF EXISTS "{rpt_name}"')
        duckdb_service.execute_ddl(f'CREATE TABLE "{rpt_name}" AS {select_sql}')
        row_count = duckdb_service.count_rows(rpt_name)
    else:
        # 业务库查询 → 物化到 DuckDB 结果库
        import pandas as pd
        from sqlalchemy import create_engine, text

        engine = create_engine(decrypt(ds.conn_info), pool_pre_ping=True)
        try:
            df = pd.read_sql(text(select_sql), engine)
        finally:
            engine.dispose()
        duckdb_service.create_table(rpt_name, df)
        row_count = len(df)

    rt = ResultTable(
        job_id=job.id,
        table_name=rpt_name,
        result_type=result.intent,
        business_name=history.question[:200],
        row_count=row_count,
        created_by=job.user_id,
    )
    db.add(rt)
    db.flush()
    job.result_table_id = rt.id
    job.status = "success"
    job.finished_at = datetime.now(UTC)
    db.commit()
    logger.info("任务 %s 完成: %s (%s 行)", job.id, rpt_name, row_count)


def _execute_sync(job_id: int) -> None:
    """eager 模式：进程内直接执行（无需 Redis/worker）。"""
    _execute(job_id)


try:
    from app.core.celery_app import celery_app

    @celery_app.task(name="jobs.execute")
    def execute_job_task(job_id: int) -> None:
        if celery_app.conf.task_always_eager:
            _execute_sync(job_id)
        else:
            # 非 eager 时该函数由 worker 进程调用，直接执行
            _execute(job_id)

except Exception:  # pragma: no cover
    logger.warning("Celery 不可用，任务退化为进程内执行")

    def execute_job_task(job_id: int) -> None:
        _execute(job_id)
