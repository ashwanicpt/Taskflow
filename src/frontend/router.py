from fastapi import APIRouter, Request, Depends, Form, status, Response, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from src.utils.db import get_db
from src.tasks import controller as task_controller
from src.user import controller as user_controller
from src.user.dtos import LoginSchema, UserSchema
from src.utils.helpers import is_authenticated
from src.user.models import UserModel
import os
from src.agent.task_agent import run_agent
from src.agent.file_import import extract_tasks_from_file, MAX_UPLOAD_BYTES
from src.agent.models import ChatHistoryModel
import uuid
from sqlalchemy import func
from src.utils.logging_config import LOG_LEVELS, read_application_logs
router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_current_user_safe(request: Request, db: Session = Depends(get_db)):
    try:
        if db is None:
            return None
        return is_authenticated(request, db)
    except:
        return None

@router.get("/", response_class=HTMLResponse)
async def home(request: Request, user: UserModel = Depends(get_current_user_safe)):
    if user:
        return RedirectResponse(url="/tasks")
    return templates.TemplateResponse(request, "login.html", {"user": user})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: UserModel = Depends(get_current_user_safe)):
    if user:
        return RedirectResponse(url="/tasks")
    return templates.TemplateResponse(request, "login.html", {"user": user})

@router.post("/login")
async def login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        login_data = LoginSchema(username=username, password=password)
        result = user_controller.login_user(login_data, db)
        token = result["token"]
        
        # Redirect to tasks and set cookie
        redirect = RedirectResponse(url="/tasks", status_code=status.HTTP_303_SEE_OTHER)
        redirect.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True)
        return redirect
    except Exception as e:
        return templates.TemplateResponse(request, "login.html", {
            "error": str(e.detail) if hasattr(e, "detail") else "Invalid credentials",
            "user": None
        })

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user: UserModel = Depends(get_current_user_safe)):
    if user:
        return RedirectResponse(url="/tasks")
    return templates.TemplateResponse(request, "register.html", {"user": user})

@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form("User"), # Default name if not provided in form
    db: Session = Depends(get_db)
):
    try:
        user_data = UserSchema(username=username, email=email, password=password, name=name)
        user_controller.register(user_data, db)
        return RedirectResponse(url="/login?msg=Registered successfully", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        return templates.TemplateResponse(request, "register.html", {
            "error": str(e.detail) if hasattr(e, "detail") else "Registration failed",
            "user": None
        })

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

@router.get("/tasks", response_class=HTMLResponse)
async def list_tasks(
    request: Request, 
    sort: str = "created_at",
    db: Session = Depends(get_db), 
    user: UserModel = Depends(is_authenticated)
):
    if db is None:
        raise HTTPException(500, detail="Database session is None in list_tasks")
    tasks_query = db.query(task_controller.TaskModel).filter(task_controller.TaskModel.user_id == user.id)
    
    if sort == "priority_desc":
        # Custom sort logic: high -> medium -> low
        from sqlalchemy import case
        tasks_query = tasks_query.order_by(
            case(
                (task_controller.TaskModel.priority == "high", 1),
                (task_controller.TaskModel.priority == "medium", 2),
                (task_controller.TaskModel.priority == "low", 3),
                else_=4
            )
        )
    elif sort == "due_date":
        tasks_query = tasks_query.order_by(task_controller.TaskModel.due_date.asc().nullslast())
    else: # Default: newest first
        tasks_query = tasks_query.order_by(task_controller.TaskModel.created_at.desc())
        
    tasks = tasks_query.all()
    # Fetch chat history for the user from agent.models
    history = db.query(ChatHistoryModel).filter(ChatHistoryModel.user_id == user.id).order_by(ChatHistoryModel.created_at.asc()).all()
    
    from datetime import datetime
    return templates.TemplateResponse(request, "index.html", {
        "tasks": tasks, 
        "user": user, 
        "sort": sort,
        "history": history,
        "today": datetime.now().date()
    })

@router.get("/logs", response_class=HTMLResponse)
async def application_logs(
    request: Request,
    level: str = "ALL",
    search: str = "",
    page: int = 1,
    user: UserModel = Depends(is_authenticated)
):
    selected_level = level.upper()
    if selected_level != "ALL" and selected_level not in LOG_LEVELS:
        raise HTTPException(status_code=400, detail="Invalid log level")
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be greater than zero")

    page_size = 100
    entries, total_entries = read_application_logs(
        level=selected_level,
        search=search[:200],
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    page_count = max(1, (total_entries + page_size - 1) // page_size)
    if page > page_count:
        raise HTTPException(status_code=404, detail="Log page not found")

    return templates.TemplateResponse(request, "logs.html", {
        "user": user,
        "entries": entries,
        "total_entries": total_entries,
        "page": page,
        "page_count": page_count,
        "selected_level": selected_level,
        "search": search[:200],
    })

@router.get("/tasks/create", response_class=HTMLResponse)
async def create_task_page(request: Request, db: Session = Depends(get_db), user: UserModel = Depends(is_authenticated)):
    history = db.query(ChatHistoryModel).filter(ChatHistoryModel.user_id == user.id).order_by(ChatHistoryModel.created_at.asc()).all()
    return templates.TemplateResponse(request, "task_form.html", {"user": user, "task": None, "history": history})

@router.post("/tasks/create")
async def create_task(
    request: Request,
    title: str = Form(...),
    description: str = Form(None),
    priority: str = Form("medium"),
    due_date: str = Form(None),
    db: Session = Depends(get_db),
    user: UserModel = Depends(is_authenticated)
):
    from src.tasks.dtos import TaskSchema
    from datetime import datetime
    dt = datetime.strptime(due_date, "%Y-%m-%d") if due_date else None
    task_data = TaskSchema(title=title, description=description, priority=priority, due_date=dt)
    task_controller.create_task(task_data, db, user)
    return RedirectResponse(url="/tasks", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/tasks/edit/{task_id}", response_class=HTMLResponse)
async def edit_task_page(task_id: int, request: Request, db: Session = Depends(get_db), user: UserModel = Depends(is_authenticated)):
    result = task_controller.getTaskById(task_id, db)
    task = result["data"] if isinstance(result, dict) and "data" in result else result
    history = db.query(ChatHistoryModel).filter(ChatHistoryModel.user_id == user.id).order_by(ChatHistoryModel.created_at.asc()).all()
    return templates.TemplateResponse(request=request, name="task_form.html", context={"user": user, "task": task, "history": history})

@router.post("/tasks/edit/{task_id}")
async def edit_task(
    task_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(None),
    is_completed: str = Form(None),
    priority: str = Form("medium"),
    due_date: str = Form(None),
    db: Session = Depends(get_db),
    user: UserModel = Depends(is_authenticated)
):
    from src.tasks.dtos import TaskSchema
    from datetime import datetime
    completed = is_completed is not None and is_completed == "on"
    dt = datetime.strptime(due_date, "%Y-%m-%d") if due_date else None
    task_data = TaskSchema(title=title, description=description, is_completed=completed, priority=priority, due_date=dt)
    task_controller.update_tasks(task_data, task_id, db, user)
    return RedirectResponse(url="/tasks", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/tasks/delete/{task_id}")
async def delete_task(task_id: int, db: Session = Depends(get_db), user: UserModel = Depends(is_authenticated)):
    task_controller.delete_task(task_id, db, user)
    return RedirectResponse(url="/tasks", status_code=status.HTTP_303_SEE_OTHER)



@router.post("/agent")
async def agent_action(
    request: Request,
    prompt: str = Form(...),
    session_id: str = Form(None),
    db: Session = Depends(get_db),
    user: UserModel = Depends(is_authenticated)
):
    # 1.Generate response from agent
    result = run_agent(prompt, db, user)
    
    # 2. Handle Session ID
    if not session_id or session_id == "null" or session_id == "undefined":
        session_id = str(uuid.uuid4())
        # First message in session sets the title
        session_title = prompt[:50] + ("..." if len(prompt) > 50 else "")
    else:
        # Check if session exists to get title, or just keep it
        existing = db.query(ChatHistoryModel).filter(ChatHistoryModel.session_id == session_id).first()
        session_title = existing.session_title if existing else (prompt[:50] + "...")

    # 3. Save to database
    new_chat = ChatHistoryModel(
        user_id=user.id, 
        session_id=session_id,
        session_title=session_title,
        prompt=prompt, 
        response=result
    )
    db.add(new_chat)
    db.commit()
    
    return {"response": result, "session_id": session_id}


@router.post("/agent/upload")
async def upload_agent_tasks(
    file: UploadFile = File(...),
    session_id: str = Form(None),
    db: Session = Depends(get_db),
    user: UserModel = Depends(is_authenticated)
):
    from src.tasks.dtos import TaskSchema

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File must be 5 MB or smaller")

    filename = (file.filename or "tasks").replace("\\", "/").split("/")[-1]
    extracted_tasks = extract_tasks_from_file(filename, content)

    existing_titles = {
        title for (title,) in db.query(task_controller.TaskModel.title)
        .filter(
            task_controller.TaskModel.user_id == user.id,
            task_controller.TaskModel.title.in_([task["title"] for task in extracted_tasks])
        )
        .all()
    }
    created_count = 0
    skipped_count = 0
    for task_data in extracted_tasks:
        title = task_data["title"]
        if title in existing_titles:
            skipped_count += 1
            continue
        task_controller.create_task(
            TaskSchema(
                title=title,
                description=task_data["description"],
                priority="medium"
            ),
            db,
            user
        )
        existing_titles.add(title)
        created_count += 1

    if created_count:
        response_text = f"Created {created_count} task(s) from {filename}."
    else:
        response_text = f"No new tasks created from {filename}."
    if skipped_count:
        response_text += f" Skipped {skipped_count} duplicate task(s)."

    prompt = f"Import tasks from {filename}"
    if not session_id or session_id in {"null", "undefined"}:
        session_id = str(uuid.uuid4())
    existing_session = db.query(ChatHistoryModel).filter(
        ChatHistoryModel.session_id == session_id,
        ChatHistoryModel.user_id == user.id
    ).first()
    session_title = existing_session.session_title if existing_session else prompt[:50]
    db.add(ChatHistoryModel(
        user_id=user.id,
        session_id=session_id,
        session_title=session_title,
        prompt=prompt,
        response=response_text
    ))
    db.commit()

    return {
        "response": response_text,
        "session_id": session_id,
        "created_count": created_count,
        "skipped_count": skipped_count
    }

@router.get("/agent/sessions")
async def get_sessions(db: Session = Depends(get_db), user: UserModel = Depends(is_authenticated)):
    # Get unique sessions for the user
    sessions = db.query(
        ChatHistoryModel.session_id, 
        ChatHistoryModel.session_title,
        func.max(ChatHistoryModel.created_at).label("last_msg")
    ).filter(ChatHistoryModel.user_id == user.id)\
     .group_by(ChatHistoryModel.session_id, ChatHistoryModel.session_title)\
     .order_by(func.max(ChatHistoryModel.created_at).desc())\
     .all()
    
    return [
        {"id": s.session_id, "title": s.session_title or "Previous Conversation"} 
        for s in sessions if s.session_id
    ]

@router.get("/agent/session/{session_id}")
async def get_session_messages(session_id: str, db: Session = Depends(get_db), user: UserModel = Depends(is_authenticated)):
    messages = db.query(ChatHistoryModel)\
        .filter(ChatHistoryModel.user_id == user.id, ChatHistoryModel.session_id == session_id)\
        .order_by(ChatHistoryModel.created_at.asc())\
        .all()
    
    return [
        {"prompt": m.prompt, "response": m.response} 
        for m in messages
    ]


@router.delete("/agent/session/{session_id}")
async def delete_session(session_id: str, db: Session = Depends(get_db), user: UserModel = Depends(is_authenticated)):
    db.query(ChatHistoryModel).filter(
        ChatHistoryModel.session_id == session_id,
        ChatHistoryModel.user_id == user.id
    ).delete()
    db.commit()
    return {"status": "deleted"}

@router.patch("/agent/session/{session_id}")
async def rename_session(
    session_id: str, 
    new_title: str = Form(...), 
    db: Session = Depends(get_db), 
    user: UserModel = Depends(is_authenticated)
):
    db.query(ChatHistoryModel).filter(
        ChatHistoryModel.session_id == session_id,
        ChatHistoryModel.user_id == user.id
    ).update({"session_title": new_title})
    db.commit()
    return {"status": "renamed", "new_title": new_title}
