import os
import json
import re
# pyrefly: ignore [missing-import]
from google import genai
from src.tasks import controller as task_controller
from sqlalchemy.orm import Session
from datetime import datetime

# Initialize client
# Connection Object to our google ai 
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# client.models.list()
# -------- TOOL FUNCTIONS -------- #

def create_task_tool(data: dict, db: Session, user):
    from src.tasks.dtos import TaskSchema
    
    task = TaskSchema(
        title=data.get("title"),
        description=data.get("description"),
        priority=data.get("priority", "medium"),
        due_date=datetime.strptime(data["due_date"], "%Y-%m-%d") if data.get("due_date") else None
    )
    
    task_controller.create_task(task, db, user)
    return "Task created successfully"


def delete_task_tool(task_id: int, db: Session, user):
    task_controller.delete_task(task_id, db, user)
    return f"Task {task_id} deleted successfully"



def delete_task_byTitle(title:str, db:Session , user):
    task_controller.delete_task_by_title(title, db, user)
    return f"Task {title} deleted successfully"


def update_task_tool(task_id: int, data: dict, db: Session, user):
    from src.tasks.dtos import TaskSchema
    
    task = TaskSchema(
        title=data.get("title"),
        description=data.get("description"),
        priority=data.get("priority", "medium"),
        is_completed=data.get("is_completed", False),
        due_date=datetime.strptime(data["due_date"], "%Y-%m-%d") if data.get("due_date") else None
    )
    
    task_controller.update_tasks(task, task_id, db, user)
    return f"Task {task_id} updated successfully"


def update_task_byTitle(title:str, data: dict, db: Session, user):
    from src.tasks.dtos import TaskSchema
    
    task = TaskSchema(
        title=data.get("title"),
        description=data.get("description"),
        priority=data.get("priority", "medium"),
        is_completed=data.get("is_completed", False),
        due_date=datetime.strptime(data["due_date"], "%Y-%m-%d") if data.get("due_date") else None
    )
    
    task_controller.update_tasks_by_title(task, title, db, user)
    return f"Task {title} updated successfully"

from src.user import controller as user_controller
def fetch_current_user_tool(user):
    return f"User Profile: Name: {user.name}, Username: {user.username}, Email: {user.email} (ID: {user.id})"
def fetch_all_users_tool(db: Session):
    users = user_controller.get_all_user(db)
    if not users:
        return "No users found in the system."
    user_list = [f"- {u.name} (@{u.username}, {u.email})" for u in users]
    return "Registered Users:\n" + "\n".join(user_list)


# Recent Task 

from src.tasks.dtos import RecentTask
def get_recent_task_tool(data: dict, db: Session, user):
    recent_dto = RecentTask(**data) if isinstance(data, dict) else data
    tasks = task_controller.get_recent_task(recent_dto, db, user)

    if not tasks:
        return "No recent tasks found."

    task_lines = []
    for t in tasks:
        status_text = "Completed" if t.is_completed else "Pending"
        priority_text = f"[{t.priority.upper()}]" if t.priority else ""
        task_lines.append(f"- ID {t.id}: {t.title} {priority_text} ({status_text})")

    return "Here are your recent tasks:\n" + "\n".join(task_lines)
    

from src.tasks.controller import delete_all_tasks
def delete_all_tasks_tool(db: Session, user):
    task_controller.delete_all_tasks(db, user)
    return "All tasks for the user have been deleted successfully."
 



# -------- JSON HELPER -------- #

def extract_json(text):
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).replace("```", "")
    decoder = json.JSONDecoder()
    results = []
    index = 0

    while index < len(text):
        if text[index] not in "[{":
            index += 1
            continue
        try:
            value, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            index += 1
            continue
        results.append(value)
        index = end

    if not results:
        return None
    if len(results) == 1:
        return results[0]
    return results
 


def run_agent(prompt: str, db: Session, user):
    
    # from Here we should send the requesst to the gemini model 
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"""
You are a task manager assistant.

You must decide whether the user is asking about task management or just having a normal conversation.

------------------------
BEHAVIOR RULES:

1. If the user request is related to tasks (create, update, delete, complete, modify tasks) or user information (current user profile, who am I, or list all users):
   - Return ONLY valid JSON
   - Do NOT include any explanation or extra text
   - Follow the exact JSON format below

2. If the user request is NOT related to tasks or users (e.g., greetings, casual chat, questions like "hello", "how are you"):
   - Respond like a normal helpful assistant
   - DO NOT return JSON
   - DO NOT mention tools or task format
3. if the user request the recent task the provide the recent task details in the JSON format 
------------------------
JSON FORMAT (ONLY for task and user-related requests):

4. if the user request is releated to delete all tasks then use the delete_all_tasks  tool 
5. For multiple task operations, return one JSON array containing one action object per task. Do not return separate JSON blocks.
6. If task title or description is not provided, generate them; use medium priority, a due date 7 days from now, and is_completed false unless specified.

Return one JSON object for a single action, or one JSON array for multiple actions. Do not wrap JSON in Markdown code fences.

{{
  "action": "create | update | delete | fetch_user | get_all_users",
  "task_id": number (required for update/delete),
  "title": string (required for delete if task_id not provided),
  "data": {{
    "title": string (optional),
    "description": string (optional),
    "priority": "low | medium | high" (optional),
    "due_date": "YYYY-MM-DD" (optional),
    "is_completed": true/false (optional)
  }}
}}

------------------------
IMPORTANT:
- Use "fetch_user" for queries like "who am I?", "my profile", "show my details", or "current user"
- Use "get_all_users" for queries like "show all users", "list users", or "get all users"
- NEVER return JSON for non-task/non-user queries
- NEVER return text for task/user queries
- Decide intent carefully before responding

------------------------
RECENT TASK FORMAT (ONLY for recent-related requests):

{{
  "action": "get_recent_task",
  "data": {{
    "title": string (optional),
    "description": string (optional),
    "priority": "low | medium | high" (optional),
    "is_completed": true/false (optional)
    "offset": number (optional),
    
  }}
}}


------------------------
User request:
{prompt}
"""
    )
    # Debug (optional)
    print("MODEL RESPONSE:", response.text)

    result = extract_json(response.text)

    if not result:
        return response.text

    if isinstance(result, list):
        if not all(isinstance(item, dict) for item in result):
            return "Invalid action format"
        results = [_dispatch_action(item, db, user) for item in result]
        return "\n".join(f"{index}. {message}" for index, message in enumerate(results, 1))

    if not isinstance(result, dict):
        return "Invalid action format"

    return _dispatch_action(result, db, user)


def _dispatch_action(result: dict, db: Session, user):
    action = result.get("action")

    if action == "create":
        return create_task_tool(result.get("data", {}), db, user)

    elif action == "delete":
        if result.get("task_id"):
            return delete_task_tool(result.get("task_id"), db, user)
        else:
            return delete_task_byTitle(result.get("title"), db, user)

    elif action == "update":
        if result.get("task_id"):
            return update_task_tool(result.get("task_id"), result.get("data", {}), db, user)
        else :
            return update_task_byTitle(result.get("title"), result.get("data", {}), db, user)


    elif action == "fetch_user":
        return fetch_current_user_tool(user)
    
    elif action == "get_all_users":


         
        return fetch_all_users_tool(db)

    elif action =="get_recent_task":
        return get_recent_task_tool(result.get("data", {}), db, user)

    elif action == "delete_all_tasks":
        return delete_all_tasks_tool(db, user)

        
        

    return "Invalid action"