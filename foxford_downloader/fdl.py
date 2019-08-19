from PyInquirer import prompt
from argparse import ArgumentParser, Namespace
import subprocess
from typing import Dict, Iterable, List, Tuple
import os
from pathlib import Path
from lib.fns import *
from lib.requests_cache import CachedSession
import atexit
from datetime import datetime


def main(params: Dict) -> None:
    session: CachedSession = CachedSession()

    credential_query: Dict[str, str]
    if params["email"] and params["password"]:
        credential_query = {"email": params["email"], "password": params["password"]}
    else:
        credential_query = prompt([
            {
                "type": "input",
                "name": "email",
                "message": "Email"
            },
            {
                "type": "password",
                "name": "password",
                "message": "Password"
            }
        ])

    if params["actions"]:
        actions = params["actions"]
    else:

        def options_check_from_actions_param(actions: str) -> Dict[str, List[str]]:
            lst = []
            if 'r' in actions:
                lst.append("Resources")
            if 'h' in actions:
                lst.append("Homework")
            if 'c' in actions:
                lst.append("Conspects")
            return {'actions': lst}

        options_check: Dict[str, List[str]] = \
            options_check_from_actions_param(params["actions"]) if params["actions"] else prompt([
                {
                    "type": "checkbox",
                    "message": "What to fetch",
                    "name": "actions",
                    "choices": [
                        {
                            "name": "Resources",
                            "checked": True
                        },
                        {
                            "name": "Homework"
                        },
                        {
                            "name": "Conspects"
                        }
                    ]
                }
            ])

        actions = ""
        if "Resources" in options_check["actions"]:
            actions += 'r'
        if "Homework" in options_check["actions"]:
            actions += 'h'
        if "Conspects" in options_check["actions"]:
            actions += 'c'

    courses_list: List[str]
    from_todo = False
    if params["course_name"]:
        courses_list = [params["course_name"]]
    else:
        try:
            with Path("todo.txt").open() as todo:
                courses_list = [line for line in todo.readlines() if line != "" and not line.isspace()]
                from_todo = True
        except FileNotFoundError:

            user_courses: Tuple[Dict] = get_user_courses(
                login(
                    credential_query["email"],
                    credential_query["password"],
                    session
                )
            )

            course_query: Dict[str, str] = prompt([
                {
                    "type": "list",
                    "name": "course_name",
                    "message": "Select course_name",
                    "choices": map(lambda obj: f"({obj['grades_range']}) {obj['name']} - {obj['subtitle']}",
                                   user_courses)
                }
            ])

            courses_list = [course_query["course_name"]]

    if from_todo:
        try:
            with Path("done.txt").open() as done_file:
                done_courses = set(done_file.readlines())
        except FileNotFoundError:
            done_courses = set()

        done_file = Path("done.txt").open('a')
        atexit.register(lambda: done_file.close())
        todo_log_file = Path("todo_log.txt").open('a')
        atexit.register(lambda: todo_log_file.close())

    exe_suff = "3" if os.name == 'posix' else ""

    for course in courses_list:
        if from_todo:
            if course in done_courses:
                continue

        print(f'Start downloading "{course}"')
        r = subprocess.run(f'python{exe_suff} fdl.py --email {credential_query["email"]}'
                           f' --password {credential_query["password"]} --course_name "{course}"'
                           f' --actions "{actions}"', shell=True)
        if from_todo:
            if r.returncode == 0:
                done_courses.add(course)
                done_file.write(course + '\n')
            else:
                todo_log_file.write(f'course "{course}" returns {r.returncode}\n')

        if from_todo:
            todo_log_file.write(f"start downloading at {datetime.now('%H:%M:%S %d.%m.%Y')}\n")


if __name__ == "__main__":
    parser: ArgumentParser = ArgumentParser()
    parser.add_argument("--email", type=str, required=False)
    parser.add_argument("--password", type=str, required=False)
    parser.add_argument("--course", type=str, required=False)
    parser.add_argument("--actions", type=str, required=False)
    args: Namespace = parser.parse_args()
    main(args.__dict__)
