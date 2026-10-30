from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class RegisterIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=24, pattern=r"^[A-Za-z0-9._-]+$")
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

class LoginIn(BaseModel):
    identity: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)

class UserOut(BaseModel):
    id: int
    full_name: str
    username: str
    email: EmailStr
    is_admin: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ActivityIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=2000)
    category: str = "Personal"
    priority: str = "Medium"
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def title_trimmed(cls, value):
        value = value.strip()
        if not value: raise ValueError("Title cannot be blank")
        return value

    @field_validator("category")
    @classmethod
    def valid_category(cls, value):
        if value not in {"Personal", "Education", "Coding", "Career", "Projects", "Health and Fitness", "Other"}: raise ValueError("Choose a valid category")
        return value

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, value):
        if value not in {"Low", "Medium", "High"}: raise ValueError("Choose a valid priority")
        return value

class ActivityOut(BaseModel):
    id: int
    user_id: int
    title: str
    description: str
    category: str
    priority: str
    due_date: date | None
    is_completed: bool
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    model_config = ConfigDict(from_attributes=True)

class CompleteIn(BaseModel): is_completed: bool
class ProgressIn(BaseModel): is_solved: bool; personal_notes: str = Field(default="", max_length=4000)
class PasswordIn(BaseModel): current_password: str; new_password: str = Field(min_length=10, max_length=128)
class ProfileIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=24, pattern=r"^[A-Za-z0-9._-]+$")
    email: EmailStr
    timezone: str = Field(min_length=1, max_length=64)
    theme: str = Field(pattern=r"^(dark|light)$")
