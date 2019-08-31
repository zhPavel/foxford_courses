import atexit
from argparse import ArgumentParser, Namespace

from PyInquirer import prompt

from foxload import download_course
from lib.fns import *
from lib.requests_cache import CachedSession


def main(params: Dict) -> None:
    session: CachedSession = CachedSession()

    email: str = params["email"] if params["email"] else prompt([
        {
            "type": "input",
            "name": "email",
            "message": "Email"
        }
    ])["email"]

    password: str = params["password"] if params["password"] else prompt([
        {
            "type": "password",
            "name": "password",
            "message": "Password"
        }
    ])["password"]

    if params["actions"] is not None:

        def options_check_from_actions_param(actions_param: str) -> List[str]:
            lst: List[str] = []
            if 'r' in actions_param:
                lst.append("Resources")
            if 'h' in actions_param:
                lst.append("Homework")
            if 'c' in actions_param:
                lst.append("Conspects")
            return lst

        actions = options_check_from_actions_param(params["actions"])
    else:

        options_check: Dict[str, List[str]] = prompt([
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

        actions = options_check["actions"]

    courses_list: List[str]
    from_todo = False

    user_courses = None
    if params["savelist"]:
        # TODO: get_user_courses() занимает очень много времени. Можно оптимизировать распараллелив, используя aiohttp
        user_courses: Tuple[Dict] = get_user_courses(
            login(
                email,
                password,
                session
            )
        )
        with Path("list.txt").open('w', encoding='utf-8') as list_file:
            list_file.write('\n'.join(
                map(lambda obj: f"({obj['grades_range']}) {obj['name']} - {obj['subtitle']}", user_courses)
            ))

    if params["course"]:
        courses_list = [params["course"]]
    else:
        try:
            with Path("todo.txt").open(encoding='utf-8') as todo:
                courses_list = [line for line in todo.readlines() if line != "" and not line.isspace()]
                from_todo = True
        except FileNotFoundError:

            if user_courses is None:
                user_courses: Tuple[Dict] = get_user_courses(
                    login(
                        email,
                        password,
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

    if not from_todo:
        download_course(email, password, courses_list[0], actions)

    else:
        try:
            with Path("done.txt").open(encoding='utf-8') as done_file:
                done_courses = set([line for line in done_file.readlines()])
        except FileNotFoundError:
            done_courses = set()
        
        with Path("todo_log.txt").open('a', encoding='utf-8') as todo_log_file:
            todo_log_file.write(f"start downloading at {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}\n")

        for course_name in courses_list:
            if course_name in done_courses:
                continue
            print(f'Start downloading "{course_name}"')
            try:
                download_course(email, password, course_name, actions)
            except Exception as e:
                from traceback import format_exception
                with Path("todo_log.txt").open('a', encoding='utf-8') as todo_log_file:
                    todo_log_file.write(f'course "{course_name}" raise exception\n')
                    todo_log_file.write(''.join(format_exception(type(e), e, e.__traceback__)))
            else:
                done_courses.add(course_name)
                done_file = Path("done.txt").open('a', encoding='utf-8')
                done_file.write(course_name + '\n')
                done_file.close()


if __name__ == "__main__":

    parser: ArgumentParser = ArgumentParser()
    parser.add_argument("--email", type=str, required=False)
    parser.add_argument("--password", type=str, required=False)
    parser.add_argument("--course", type=str, required=False)
    parser.add_argument("--actions", type=str, required=False)
    parser.add_argument('--savelist', action='store_true', required=False)
    args: Namespace = parser.parse_args()
    # import cProfile
    # cProfile.run("main(args.__dict__)")
    main(args.__dict__)
