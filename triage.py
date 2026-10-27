from typing import Literal
from pydantic import BaseModel, Field, field_validator
from clinical.algorithms.news2.calculator import ConsciousnessLevel

IDPAT = r"^[A-Za-z0-9_-]{1,64}$"
Role = Literal["admin", "clinician", "auditor"]

class PatientIn(BaseModel):
    patient_id: str = Field(pattern=IDPAT)
    full_name: str = Field(min_length=1, max_length=200)
    age: int = Field(ge=0, le=120)
    gender: Literal["male", "female", "other", "unknown"]

class VitalsIn(BaseModel):
    respiratory_rate: int = Field(ge=1, le=70)
    oxygen_saturation: int = Field(ge=50, le=100)
    supplemental_oxygen: bool
    spo2_scale_2: bool = False
    systolic_bp: int = Field(ge=40, le=300)
    heart_rate: int = Field(ge=20, le=250)
    consciousness: ConsciousnessLevel
    temperature: float = Field(ge=30.0, le=45.0)
    @field_validator("temperature")
    @classmethod
    def _one_decimal(cls, v): return round(v, 1)

class EvaluateIn(BaseModel):
    patient_id: str = Field(pattern=IDPAT)
    vitals: VitalsIn

class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]{3,64}$")
    password: str = Field(min_length=12, max_length=128)
    role: Role

class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
