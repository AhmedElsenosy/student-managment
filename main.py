from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.routes import assistant
from app.routes import student
from app.routes import course
from app.routes import exam
from app.routes import group
from app.routes import attendance
from app.routes import monthsale
from app.routes import booksale
from app.routes import outgoing
from app.routes import finance
from app.routes import archive_management
from app.routes import financial_reports
from app.routes import blacklist
from app.routes import internal
from app.routes import inventory
from app.models.exam import ExamModel
from app.models.student_document import StudentDocument
from app.models.student import StudentModel
from app.models.counter import Counter
from app.models.group import Group
from app.models.monthsale import MonthlySale
from app.models.booksale import BookSale  
from app.models.student_default_price import StudentDefaultPrice
from app.models.outgoing import Outgoing
from app.models.archived_student import ArchivedStudentModel
from app.models.blacklist import BlacklistStudent
from app.config import settings
from fastapi.staticfiles import StaticFiles
import os
from fastapi.middleware.cors import CORSMiddleware




app = FastAPI()

@app.on_event("startup")
async def app_init():
    client = AsyncIOMotorClient(settings.MONGO_URI)  
    db = client[settings.DATABASE_NAME]             

    await init_beanie(
        database=db,
        document_models=[
            ExamModel,
            StudentDocument,
            StudentModel,
            Counter,
            Group,
            MonthlySale,
            StudentDefaultPrice,
            BookSale,
            Outgoing,
            ArchivedStudentModel,
            BlacklistStudent,
        ]
    )


app.mount(
    "/solutions",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "upload/solutions")),
    name="solutions"
)

app.mount(
    "/student_solutions",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "upload/student_solutions")),
    name="student_solutions"
)


app.include_router(assistant.router)
app.include_router(student.router)
app.include_router(course.router)
app.include_router(exam.router)
app.include_router(group.router)
app.include_router(attendance.router)
app.include_router(monthsale.router)
app.include_router(booksale.router)
app.include_router(outgoing.router)
app.include_router(finance.router)
app.include_router(archive_management.router)
app.include_router(financial_reports.router)
app.include_router(blacklist.router)
app.include_router(internal.router)
app.include_router(inventory.router)


@app.get("/")
def root():
    return {"message": "Assistant Auth API Running"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)