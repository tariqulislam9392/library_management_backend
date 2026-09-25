from calendar import c

from fastapi import FastAPI,APIRouter , Depends
from pydantic import BaseModel, Field
from sqlalchemy import over
from models import Books, Column, IssueRicord, Reservations, Users 
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

from router.auth import get_current_user

router = APIRouter()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()

class BookCreate(BaseModel):
    title : str
    author : str
    category : str
    description : str = Field(default='', max_length=500)
    price : float =Field(default=0.0, ge=0.0)
    total_copies : int = Field(default=1, ge=0)

class BookUpdate(BaseModel):
    title : Optional[str] = Field(default=None)
    author : Optional[str] = Field(default=None)
    category : Optional[str] = Field(default=None)
    description : Optional[str] = Field(default=None, max_length=500)
    price : Optional[float] = Field(default=None, ge=0.0)
    total_copies : Optional[int] = Field(default=None, ge=0)
    available : Optional[int] = Field(default=None, ge=0)

class IssueBook(BaseModel):
    book_id: int
    user_id: int

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict,Depends(get_current_user)]

def calculate_fine(due_date: datetime, return_date: datetime) -> float:
    overdue_days = (return_date.date() - due_date.date()).days
    if overdue_days > 0:
        fine_amount = overdue_days * 1.0  # Assuming $1 fine per day
        return round(fine_amount, 2)  # Round to 2 decimal places
    else:
        return 0.0

@router.post('/admin/create_book')
def create_book(new_book: BookCreate, db: db_dependency, user: user_dependency):
    if user is None or user.get('role') != 'librarian':
        raise HTTPException(status_code=401, detail='You are not authorized to perform this action')
    existing_book = db.query(Books).filter(
        Books.title == new_book.title,
        Books.author == new_book.author
    ).first()

    # যদি আগে থেকেই থাকে
    if existing_book:
        raise HTTPException(
            status_code=400,
            detail='This book already exists'
        )
    
    book_model = Books(
        **new_book.model_dump(),
        available=new_book.total_copies
    )
    db.add(book_model)
    db.commit()
    return JSONResponse(content={'message': 'Book created successfully'}, status_code=201)




@router.put('/admin/update_book/{book_id}')
def update_book(book_id: int, update_book: BookUpdate, db: db_dependency, user: user_dependency):
    if user is None or user.get('role') != 'librarian':
        raise HTTPException(status_code=401, detail='You are not authorized to perform this action')
    
    book = db.query(Books).filter(Books.id == book_id).first()
    if book is None:
        raise HTTPException(status_code=404, detail='Book not found')
    
    update_data = update_book.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(book, key, value)
    db.commit()
    return JSONResponse(content={'message': 'Book updated successfully'}, status_code=200)\

@router.delete('/admin/delete_book/{book_id}')
def delete_book(book_id: int, db: db_dependency, user: user_dependency):
    if user is None or user.get('role') != 'librarian':
        raise HTTPException(status_code=401, detail='You are not authorized to perform this action')
    
    book = db.query(Books).filter(Books.id == book_id).first()
    if book is None:
        raise HTTPException(status_code=404, detail='Book not found')
    
    db.delete(book)
    db.commit()
    return JSONResponse(content={'message': 'Book deleted successfully'}, status_code=200)
 

@router.post('/admin/create_issue')
def create_issue(user: user_dependency, db: db_dependency, issue_request: IssueBook):
    if user is None or user.get('role') != 'librarian':
        raise HTTPException(status_code=401, detail='You are not authorized to perform this action')
    
    book = db.query(Books).filter(Books.id == issue_request.book_id).first()
    if book is None:
        raise HTTPException(status_code=404, detail='Book not found')
    member = db.query(Users).filter(Users.id == issue_request.user_id).first()
    if member is None:
        raise HTTPException(status_code=404, detail='Member not found')
    if book.available <= 0:
        raise HTTPException(status_code=400, detail='No available copies of the book')
    loan_days = 14
    issue_date = datetime.now
    issue_record = IssueRicord(
        book_id=issue_request.book_id,
        user_id=issue_request.user_id,
        issue_date=issue_date,
        due_date=issue_date + timedelta(days=loan_days),
        status='issued'
    )
    book.available -= 1

    reservation = db.query(Reservations).filter(
        Reservations.book_id == issue_request.book_id, 
        Reservations.user_id == issue_request.user_id, 
        Reservations.status == 'pending'
        )
    if reservation is not None:
        reservation.status = 'completed'
    db.add(issue_record)
    db.commit()
    return JSONResponse(content={'message': 'Book issued successfully'}, status_code=201)

@router.put('/admin/return_book/{issue_id}')
def return_book(issue_id: int, db: db_dependency, user: user_dependency):
    if user is None or user.get('role') != 'librarian':
        raise HTTPException(status_code=401, detail='You are not authorized to perform this action')
    
    issue = db.query(IssueRicord).filter(IssueRicord.id == issue_id).first()
    if issue is None:
        raise HTTPException(status_code=404, detail='Issue record not found')
    return_date = datetime.now()
    find = calculate_fine(issue.due_date, return_date)

    issue.return_date = return_date
    issue.status = 'returned'
    issue.find_amount = find
    book = db.query(Books).filter(Books.id == issue.book_id).first()
    if book is None:
        book.available += 1
    
    db.commit()
    return JSONResponse(content={'message': 'Book returned successfully', 'fine_amount': find}, status_code=200)

@router.put('/admin/fine/pay/{issue_id}')
def fine_paid(issue_id: int, db: db_dependency, user: user_dependency):
    if user is None or user.get('role') != 'librarian':
        raise HTTPException(status_code=401, detail='You are not authorized to perform this action')
    
    issue = db.query(IssueRicord).filter(IssueRicord.id == issue_id).first()
    if issue is None:
        raise HTTPException(status_code=404, detail='Issue record not found')
    
    issue.fine_paid = True
    db.commit()
    return JSONResponse(content={'message': 'Fine marked as paid successfully'}, status_code=200)