from itertools import chain
from multiprocessing import Pool, cpu_count

from lib.browser import BrowserConnectionManager
from lib.fns import *
from lib.helpers import Logger, pipe
from lib.requests_cache import CachedSession


def download_course_json(email: str, password: str) -> None:
    session: CachedSession = CachedSession()
    credential_query: Dict[str, str] = {"email": email, "password": password}

    Logger.log("Fetching course list...")

    user_courses: Tuple[Dict] = get_user_courses(
        login(
            credential_query["email"],
            credential_query["password"],
            session
        )
    )

    with Path("todo.txt").open(encoding='utf-8') as todo:
        courses_list = [line for line in todo.readlines() if line != "" and not line.isspace()]

        with Path("done.txt").open(encoding='utf-8') as done_file:
            done_courses = set([line.rstrip() for line in done_file.readlines()])

        for course_name in courses_list:
            course_name = course_name[:-1]

            if course_name not in done_courses:
                Logger.log("Fetching lesson list...")

                print(repr(course_name))

                try:
                    selected_course: Dict = next(
                        filter(
                            lambda obj: f"({obj['grades_range']}) {obj['name']} - {obj['subtitle']}" == course_name,
                            user_courses
                        )
                    )
                except StopIteration:
                    import sys
                    print("Bad course name", file=sys.stderr)
                    raise

                (
                    course_lessons_with_video,
                    course_lessons_with_homework,
                    course_lessons_with_conspect
                ) = pipe(
                    lambda course_id: get_course_lessons(course_id, session),
                    lambda all_lessons: filter(
                        lambda lesson: lesson["access_state"] == "available" and not lesson["is_locked"],
                        all_lessons
                    ),
                    tuple,
                    lambda available_lessons: map(
                        lambda that_include: filter(
                            # Бывает 'available' | 'none', бывает 'webinar_available' | 'webinar_not_available'
                            lambda lesson: "available" in lesson[f"{that_include}_status"]
                                           and
                                           "not_available" not in lesson[f"{that_include}_status"],
                            available_lessons
                        ), [
                            "webinar",
                            "homework",
                            "conspect"
                        ]
                    ),
                    lambda map_of_filters: map(tuple, map_of_filters)
                )(selected_course["resource_id"])

                Logger.warn("Resources collection started")
                Logger.log("Fetching resources links...")

                resources_for_lessons: Tuple[Dict] = get_resources_for_lessons(
                    selected_course["resource_id"],
                    map(
                        lambda obj: obj["webinar_id"],
                        course_lessons_with_video
                    ),
                    session
                )

                paths: Iterable[Path] = build_dir_hierarchy(
                    selected_course["name"],
                    selected_course["subtitle"],
                    selected_course["grades_range"],
                    course_lessons_with_video
                )

                Logger.log("Downloading resources...")

                for res_with_path, session in map(
                        lambda res_obj, path: [
                            {
                                **res_obj,
                                "destination": path
                            },
                            session
                        ],
                        resources_for_lessons,
                        paths
                    ):
                    download_events_json(res_with_path, session)

                Logger.warn("Resources collection finished")

                done_courses.add(course_name)
                done_file = Path("done.txt").open('a', encoding='utf-8')
                done_file.write(course_name + '\n')
                done_file.close()


download_course_json("p917910@gmail.com", "gfdkeirf21")
