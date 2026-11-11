from pydantic import BaseModel


class UserSchema(BaseModel):
    name:str
    username:str
    password:str
    email:str




class UserResponseSchema(BaseModel):

    name:str
    username:str
    # hash_password:str
    email:str


class LoginSchema(BaseModel):
    username:str
    password:str



class GetAllUser(BaseModel):
    id: int
    name: str
    username: str
    email: str

    model_config = {"from_attributes": True}