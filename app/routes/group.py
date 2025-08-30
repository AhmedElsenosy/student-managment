from fastapi import APIRouter, Depends, HTTPException
from app.models.group import Group
from app.schemas.group import GroupCreate, GroupUpdate, GroupOut
from app.models.student_document import StudentDocument
from app.schemas.group import AddStudentToGroup
from app.schemas.group import GroupWithStudentsOut, StudentInGroupOut
from app.dependencies.auth import get_current_assistant
from app.models.group import PyObjectId
from typing import List

router = APIRouter(
    prefix="/groups",
    tags=["Groups"],
    dependencies=[Depends(get_current_assistant)]
)


@router.post("/", response_model=GroupOut)
async def create_group(group: GroupCreate):
    new_group = Group(**group.dict())
    await new_group.insert()
    return GroupOut(id=str(new_group.id), **group.dict())


@router.get("/", response_model=List[GroupOut])
async def get_all_groups():
    groups = await Group.find_all().to_list()
    return [GroupOut(
        id=str(group.id),
        group_name=group.group_name,
        start_time=group.start_time,
        level=group.level,
        days=group.days,
        student_count=len(group.students) if group.students else 0
    ) for group in groups]


@router.put("/{group_id}")
async def update_group(group_id: str, data: GroupUpdate):
    group = await Group.get(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    update_data = data.dict(exclude_unset=True)  # Only update provided fields
    for key, value in update_data.items():
        setattr(group, key, value)

    await group.save()
    return {"message": "Group updated successfully"}



@router.delete("/{group_id}")
async def delete_group(group_id: str):
    group = await Group.get(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    await group.delete()
    return {"message": "Group deleted successfully"}



@router.post("/{group_id}/add-student")
async def add_student_to_group(group_id: str, payload: AddStudentToGroup):
    try:
        group_obj_id = PyObjectId(group_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid group ID: {e}")

    group = await Group.get(group_obj_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    try:
        student_obj_id = PyObjectId(payload.student_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid student ID: {e}")

    student = await StudentDocument.get(student_obj_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Remove student from any other group
    other_groups = await Group.find(Group.students == student_obj_id).to_list()
    for other_group in other_groups:
        if other_group.id != group.id:
            other_group.students.remove(student_obj_id)
            await other_group.save()

    # Add to new group if not already present
    if student_obj_id not in group.students:
        group.students.append(student_obj_id)
        await group.save()
        return {"message": "Student moved to new group successfully"}
    else:
        return {"message": "Student already in this group"}

@router.get("/{group_id}", response_model=GroupWithStudentsOut)
async def get_group_by_id(group_id: str):
    try:
        group_obj_id = PyObjectId(group_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid group ID: {e}")

    group = await Group.get(group_obj_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    students_out = []
    for student_id in group.students:
        student = await StudentDocument.get(student_id)
        if student:
            students_out.append(StudentInGroupOut(
                student_name=f"{student.first_name} {student.last_name}",
                level=student.level,
                phone_number=student.phone_number,
                guardian_number=student.guardian_number,
                is_subscription=student.is_subscription,
                group_name=group.group_name
            ))

    return GroupWithStudentsOut(
        group_id=str(group.id),
        group_name=group.group_name,
        level=group.level,
        students=students_out
    )
