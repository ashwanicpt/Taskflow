from  src.user.dtos import UserSchema , LoginSchema
from sqlalchemy.orm import Session 
from src.user.models import UserModel
from fastapi import HTTPException ,status,Request
from pwdlib import PasswordHash
import jwt 
from jwt.exceptions import InvalidTokenError
from src.utils.settings import settings
from datetime import datetime, timedelta

password_hash=PasswordHash.recommended()

def get_password_hash(password):
    return password_hash.hash(password)

def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password,hashed_password)

def register(body:UserSchema, db:Session):
    if db is None:
        raise HTTPException(500, detail="Database session is None in register")
    is_user=db.query(UserModel).filter(UserModel.username==body.username).first()
    if is_user : 
        raise HTTPException(400,detail="UserName Already Exists")

    is_user=db.query(UserModel).filter(UserModel.email==body.email).first()
    if is_user:
        raise HTTPException(400,detail="Email Already Exist")
    
    hash_password=get_password_hash(body.password)
    new_user=UserModel(
        name=body.name,
        username=body.username,
        hash_password=hash_password,
        email=body.email
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
    
def login_user(body:LoginSchema, db:Session):
    if db is None:
        raise HTTPException(500, detail="Database session is None in login_user")
    user=db.query(UserModel).filter(UserModel.username==body.username).first()
    if not user: 
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail=f"user not exist {body.username}")
    if not verify_password(body.password, user.hash_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail=f"you Enter the wrong password {body.password}")
    
    exp_time=datetime.now() + timedelta(minutes=settings.EXP_Time)
    token=jwt.encode({"_id":user.id, "username":user.username,"exp":exp_time.timestamp()},settings.SECRET_KEY,
    settings.ALGORITHM)
    return { "message":f"User Login successfully  {user.username}"
        ,"token":token}




def get_all_user(db:Session):
    return db.query(UserModel).all()