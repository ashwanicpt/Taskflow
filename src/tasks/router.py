from fastapi import APIRouter , Depends ,status
from src.tasks import controller
from src.tasks.dtos import TaskSchema,TaskResponseSchema
from src.utils.db import get_db
from src.tasks.dtos import MultipleCond
from typing import List
from src.utils.helpers import is_authenticated
from src.user.models import UserModel
# ApiRoutes are used to orgainze the routes into seperate file 
# OR if we want to make the 
task_routes=APIRouter(prefix="/tasks")

# Here we call the method of the controller 
# response_model are used to provide the response schema 

@task_routes.post("/create", response_model=TaskResponseSchema,status_code=status.HTTP_201_CREATED)
# Depends is like a autowired in the spring boot which automatically inject its db dependencies here
def create_task(body:TaskSchema,db=Depends(get_db), user:UserModel=Depends(is_authenticated)):   
    print("Creted")  
    if db is None:
        raise HTTPException(status_code=500, detail="Database session is None in API create_task")
    print(user.id)
    # after getting the db connection we will pass it to create_task 
    return controller.create_task(body,db,user)

# https://127.0.0.1:8000/task/create_task



# Get all tasks
@task_routes.get("/getTasks",response_model=List[TaskResponseSchema],status_code=status.HTTP_200_OK)
def get_task(db=Depends(get_db),user:UserModel=Depends(is_authenticated)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database session is None in API get_task")
    return controller.get_tasks(db,user)



# get taks by id 
 
@task_routes.get("/getTasks/{id}",status_code=status.HTTP_200_OK)
def get_taskById(id:int , db=Depends(get_db), user:UserModel=Depends(is_authenticated)):
    return controller.getTaskById(id, db)


# filter by various conditions 
@task_routes.get("/filter",status_code=status.HTTP_200_OK)
def get_mul_cond(body:MultipleCond,db=Depends(get_db)):
    return controller.getByMulCond(body,db)




# Update the Task 

@task_routes.put("/update/tasks/{task_id}",status_code=status.HTTP_201_CREATED)
def update_taks(body:TaskSchema,task_id:int, db=Depends(get_db),user:UserModel=Depends(is_authenticated)):
    return controller.update_tasks(body,task_id,db,user)



# Delete task 

@task_routes.delete("/tasksDelete/{task_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id:int, db=Depends(get_db),user:UserModel=Depends(is_authenticated)):
     
    return controller.delete_task(task_id,db,user)

 

from src.tasks.dtos import RecentTask


@task_routes.get("/recents",response_model=List[TaskResponseSchema],status_code=status.HTTP_200_OK)
def get_recent_task(body:RecentTask, db=Depends(get_db),user:UserModel=Depends(is_authenticated)):
    return controller.get_recent_task(body, db, user)