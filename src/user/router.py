from fastapi import APIRouter , Depends ,status , Request 
from src.user.dtos import UserSchema,UserResponseSchema,LoginSchema , GetAllUser
from src.user import controller
from sqlalchemy.orm import Session 
from src.utils.db import get_db
from src.utils.helpers import is_authenticated
from src.user.models import UserModel

user_routes=APIRouter(prefix="/user")

@user_routes.post("/register",response_model=UserResponseSchema,status_code=status.HTTP_201_CREATED)
def register(body:UserSchema , db:Session=Depends(get_db)):
    return controller.register(body,db)


@user_routes.post("/login",status_code=status.HTTP_200_OK)
def login(body:LoginSchema,db:Session=Depends(get_db)):
    return controller.login_user(body,db)


@user_routes.get("/is_auth",status_code=status.HTTP_200_OK , response_model=UserResponseSchema)
def is_auth(user:UserModel=Depends(is_authenticated)):
    return user




@user_routes.get("/all",response_model=list[GetAllUser])
def get_all_users(db:Session=Depends(get_db)):
    return controller.get_all_user(db)