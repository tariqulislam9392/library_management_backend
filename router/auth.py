from fastapi import FastAPI,APIRouter , Depends
from httpx import get
from pydantic import BaseModel, Field
from models import Users 
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Annotated
from database import SessionLocal
from fastapi.security import OAuth2PasswordRequestForm,OAuth2PasswordBearer
from jose import jwt,JWTError
from datetime import timedelta,datetime,timezone
from fastapi import HTTPException
from typing import Optional
from passlib.context import CryptContext

router = APIRouter()

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
OAuth2_Bearer = OAuth2PasswordBearer(tokenUrl='login')

SECRET_KEY = '2e377defd231614384e5f4593be866286ff6ef685d5357484a2e5759bc2b0f76'
ALGORITHAM = 'HS256'



class Creatusers(BaseModel):
    email : str
    username : str
    firstname : str
    lastname :  str
    password : str
    role : str
    # phone_number : str

class Updateuser(BaseModel):
    email: Optional[str] = Field(default=None)
    username : Optional[str] = Field(default=None)
    firsatname : Optional[str] = Field(default=None)
    lastname : Optional[int] = Field(default=None)
    # phone_number : Optional[str] = Field(default=None)

class UpdatePassword(BaseModel):
    current_password: str
    new_password:str


def authenticate_user(username, password, db):
    user  = db.query(Users).filter(Users.username == username).first()
    if user is None:
        return False
    if bcrypt_context.verify(password, user.hash_password):
        return user
    return False


def create_access_token(username: str, user_id: int, role: str, expires_delta: timedelta):
    encode = {'sub': username, 'id': user_id , 'role': role}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode,SECRET_KEY,algorithm= ALGORITHAM)

def get_current_user(token: Annotated[str, Depends(OAuth2_Bearer)]):
    try:
        payload = jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHAM])
        username: str = payload.get('sub')
        user_id: int = payload.get('id')
        role: str = payload.get('role')
        if username is None or user_id is None:
            raise HTTPException(status_code=404, detail="user not found")
        return {'username': username, 'id': user_id, 'role': role}
    except:
        raise HTTPException(status_code=404, detail="user not found")


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict,Depends(get_current_user)]


@router.post('/createuser')
def create_Users( db : db_dependency, new_user : Creatusers):
    user_model = Users(
        email = new_user.email ,
        username = new_user.username,
        firstname = new_user.firstname ,
        lastname = new_user.lastname ,
        hash_password = bcrypt_context.hash(new_user.password),
        is_active = True,
        role= new_user.role,
        # phone_number = new_user.phone_number
    )
    db.add(user_model)
    db.commit()
    # db.refresh(todo_model)
    # return todo_model
    

    return JSONResponse(status_code=201, content={'massage': 'to do created successfully'})

@router.post('/login')
def login_user(db : db_dependency, from_data : Annotated[OAuth2PasswordRequestForm,Depends()]):

# def authenticate_user(username, password, db):
#     user = specific_todos = db.query(users).filter(users.username == username).first()
#     if user is None:
#         return False
#     if bcrypt_context.verify(password, user.hash_password):
#         return True
#     return False

    user = authenticate_user(from_data.username, from_data.password,db)

    if not user:
        raise HTTPException(status_code=404, detail='Faild Authentication')
    token = create_access_token(user.username, user.id, user.role, timedelta(minutes=30))
    return {'access_token': token , 'token_type' : 'bearer'}  



@router.put('/edituser')
def update_user(user: user_dependency,db: db_dependency,  update_user: Updateuser):
    if user is None:
        raise HTTPException(status_code=404, detail='Faild Authentication')
    user = db.query(Users).filter(Users.id == user.get('id')).first()

    update_data = update_user.model_dump(exclude_unset= True)
    for key, value in update_data.items():
        setattr(user, key, value)
    db.commit()


    return JSONResponse(status_code=200, content={'massage': 'user updated successfully'})




@router.put('/paswordchange')
def update_password(user: user_dependency,db: db_dependency,  update_password: UpdatePassword):
    if user is None:
        raise HTTPException(status_code=404, detail='Faild Authentication')
    user = db.query(Users).filter(Users.id == user.get('id')).first()

    if not bcrypt_context.verify(update_password.current_password, user.hash_password):
        raise HTTPException(status_code=404, detail='Wrong password')
    user.hash_password = bcrypt_context.hash(update_password.new_password)
    db.add(user)

    db.commit()


    return JSONResponse(status_code=200, content={'massage': 'Password updated successfully'})



@router.get('/user')
def get_user_profile(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication Failed')
    
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    if user_model is None:
        raise HTTPException(status_code=404, detail='User not found')
        
    return {
        "id": user_model.id,
        "username": user_model.username,
        "email": user_model.email,
        "firstname": user_model.firstname,
        "lastname": user_model.lastname,
        "role": user_model.role
    }