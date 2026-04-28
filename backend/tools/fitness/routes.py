from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.db.connection import get_db

router = APIRouter()
BodyPart = Literal["arms", "shoulders", "abs"]


class ExercisePayload(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    bodyPart: BodyPart
    sets: int = Field(ge=1, le=50)
    reps: int = Field(ge=1, le=200)
    restSeconds: int = Field(ge=1, le=600)


class CompletedExercisePayload(BaseModel):
    exerciseId: str = Field(min_length=1)
    exerciseName: str = Field(min_length=1)
    bodyPart: BodyPart
    completedSets: int = Field(ge=1, le=200)
    totalSets: int = Field(ge=1, le=200)
    completedAt: datetime


@router.get("/exercises")
def get_exercises(bodyPart: BodyPart | None = None):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                if bodyPart:
                    cur.execute(
                        """
                        SELECT id, name, body_part, sets, reps, rest_seconds
                        FROM fitness.exercises
                        WHERE body_part = %s
                        ORDER BY created_at
                        """,
                        (bodyPart,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, name, body_part, sets, reps, rest_seconds
                        FROM fitness.exercises
                        ORDER BY body_part, created_at
                        """
                    )
                rows = cur.fetchall()

        return [
            {
                "id": r[0],
                "name": r[1],
                "bodyPart": r[2],
                "sets": r[3],
                "reps": r[4],
                "restSeconds": r[5],
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch exercises: {e}")


@router.post("/exercises")
def save_exercise(payload: ExercisePayload):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fitness.exercises
                        (id, name, body_part, sets, reps, rest_seconds, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        body_part = EXCLUDED.body_part,
                        sets = EXCLUDED.sets,
                        reps = EXCLUDED.reps,
                        rest_seconds = EXCLUDED.rest_seconds,
                        updated_at = NOW()
                    """,
                    (
                        payload.id,
                        payload.name,
                        payload.bodyPart,
                        payload.sets,
                        payload.reps,
                        payload.restSeconds,
                    ),
                )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save exercise: {e}")


@router.delete("/exercises/{exercise_id}")
def delete_exercise(exercise_id: str):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM fitness.exercises WHERE id = %s", (exercise_id,))
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete exercise: {e}")


@router.get("/logs")
def get_logs(log_date: date | None = None):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                if log_date:
                    cur.execute(
                        """
                        SELECT exercise_id, exercise_name, body_part, completed_sets, total_sets, completed_at, log_date
                        FROM fitness.workout_logs
                        WHERE log_date = %s
                        ORDER BY completed_at
                        """,
                        (log_date,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT exercise_id, exercise_name, body_part, completed_sets, total_sets, completed_at, log_date
                        FROM fitness.workout_logs
                        ORDER BY completed_at DESC
                        LIMIT 500
                        """
                    )
                rows = cur.fetchall()

        grouped: dict[str, dict] = {}
        for r in rows:
            date_key = r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6])
            grouped.setdefault(date_key, {"date": date_key, "completedExercises": []})
            grouped[date_key]["completedExercises"].append(
                {
                    "exerciseId": r[0],
                    "exerciseName": r[1],
                    "bodyPart": r[2],
                    "completedSets": r[3],
                    "totalSets": r[4],
                    "completedAt": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5]),
                }
            )
        return list(grouped.values())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch logs: {e}")


@router.post("/logs")
def save_log(payload: CompletedExercisePayload):
    try:
        log_date = payload.completedAt.date()
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fitness.workout_logs
                        (exercise_id, exercise_name, body_part, completed_sets, total_sets, completed_at, log_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        payload.exerciseId,
                        payload.exerciseName,
                        payload.bodyPart,
                        payload.completedSets,
                        payload.totalSets,
                        payload.completedAt,
                        log_date,
                    ),
                )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save log: {e}")
