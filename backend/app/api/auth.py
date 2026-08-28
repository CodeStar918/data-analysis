"""登录与当前用户接口。"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, CurrentUser, LoginRequest, LoginResponse
from app.services.audit_service import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    ip = request.client.host if request.client else ""
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        audit(db, 0, body.username, "login_failed", "用户名或密码错误", ip, commit=True)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if not user.is_active:
        audit(db, user.id, user.username, "login_failed", "账号已禁用", ip, commit=True)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已禁用")

    token = create_access_token(user.id, user.username)
    audit(db, user.id, user.username, "login", "登录成功", ip, commit=True)
    return LoginResponse(access_token=token, username=user.username, role=user.role)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "令牌无效或已过期")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已禁用")
    return CurrentUser(id=user.id, username=user.username, role=user.role, dept=user.dept)


@router.get("/me", response_model=CurrentUser)
def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return user


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """管理员权限：admin / dept_admin 可用。"""
    if user.role not in ("admin", "dept_admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """自助修改密码：校验旧密码，新密码至少 8 位。"""
    ip = request.client.host if request.client else ""
    row = db.get(User, user.id)
    if row is None or not verify_password(body.old_password, row.password_hash):
        audit(db, user.id, user.username, "password_change", "修改失败：旧密码错误", ip, commit=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "旧密码错误")
    if verify_password(body.new_password, row.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "新密码不能与旧密码相同")

    row.password_hash = hash_password(body.new_password)
    db.commit()
    audit(db, user.id, user.username, "password_change", "密码修改成功", ip, commit=True)
    return {"message": "密码已修改，请重新登录"}
