"""
course_enrollment_portal/models.py
==================================
Data models for Problem Statement 7: Online Course Enrollment Portal.
Covers Student Registration, Course Catalog, Time Slots, and Enrollment Records.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import time


@dataclass
class TimeSlot:
    """Represents a weekly meeting slot for a course."""
    day: str             # e.g. "Monday", "Wednesday", "Friday"
    start_time: str      # e.g. "10:00" (HH:MM 24-hr)
    end_time: str        # e.g. "11:30" (HH:MM 24-hr)

    def to_minutes(self) -> tuple[int, int]:
        """Convert HH:MM start and end times to minutes from midnight."""
        sh, sm = map(int, self.start_time.split(":"))
        eh, em = map(int, self.end_time.split(":"))
        return (sh * 60 + sm, eh * 60 + em)

    def overlaps_with(self, other: "TimeSlot") -> bool:
        """Return True if days match and time intervals overlap."""
        if self.day.strip().lower() != other.day.strip().lower():
            return False
        s1, e1 = self.to_minutes()
        s2, e2 = self.to_minutes()
        # Intervals overlap if start1 < end2 and start2 < end1
        return max(s1, s2) < min(e1, e2)


@dataclass
class Course:
    """Represents an academic course offering."""
    course_code: str                  # e.g. "CS101", "MATH201"
    title: str                        # e.g. "Introduction to Computer Science"
    instructor: str                   # e.g. "Dr. Alan Turing"
    credits: int                      # e.g. 3 or 4
    prerequisites: List[str] = field(default_factory=list)  # list of course_codes
    max_capacity: int = 50
    current_enrolled: int = 0
    time_slots: List[TimeSlot] = field(default_factory=list)

    @property
    def is_full(self) -> bool:
        return self.current_enrolled >= self.max_capacity


@dataclass
class Student:
    """Represents a registered student."""
    student_id: str                   # e.g. "STU-2026-001"
    name: str                         # e.g. "Balaj R."
    email: str                        # e.g. "balaj@university.edu"
    major: str                        # e.g. "Computer Science"
    completed_courses: List[str] = field(default_factory=list)  # e.g. ["MATH100"]
    enrolled_courses: List[str] = field(default_factory=list)   # e.g. ["CS101"]


@dataclass
class EnrollmentRecord:
    """Audit log of an enrollment event."""
    enrollment_id: str
    student_id: str
    course_code: str
    status: str                       # "ENROLLED", "WAITLISTED", "DROPPED", "REJECTED_CONFLICT"
    reason: Optional[str] = None
