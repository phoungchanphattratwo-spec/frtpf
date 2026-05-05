"""
Random English name generator used during auto-registration.
"""

from __future__ import annotations
import random

_FIRST_NAMES_MALE = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard",
    "Joseph", "Thomas", "Charles", "Christopher", "Daniel", "Matthew",
    "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua",
    "Kenneth", "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward",
    "Jason", "Jeffrey", "Ryan", "Jacob", "Gary", "Nicholas", "Eric",
    "Jonathan", "Stephen", "Larry", "Justin", "Scott", "Brandon",
]

_FIRST_NAMES_FEMALE = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth",
    "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty",
    "Margaret", "Sandra", "Ashley", "Dorothy", "Kimberly", "Emily",
    "Donna", "Michelle", "Carol", "Amanda", "Melissa", "Deborah",
    "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia", "Kathleen",
    "Amy", "Angela", "Shirley", "Anna", "Brenda", "Pamela", "Emma",
    "Nicole", "Helen",
]

_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
]


def random_first_name(gender: str = "Male") -> str:
    """Return a random first name for the given gender."""
    pool = _FIRST_NAMES_FEMALE if gender.lower() in ("female", "f") else _FIRST_NAMES_MALE
    return random.choice(pool)


def random_last_name() -> str:
    """Return a random last name."""
    return random.choice(_LAST_NAMES)


def random_full_name(gender: str = "Male") -> tuple[str, str]:
    """Return (first_name, last_name) tuple."""
    return random_first_name(gender), random_last_name()


def generate_name_list(count: int, gender: str = "Male") -> list[tuple[str, str]]:
    """Generate *count* unique (first, last) name pairs."""
    names = set()
    attempts = 0
    while len(names) < count and attempts < count * 10:
        names.add(random_full_name(gender))
        attempts += 1
    return list(names)
