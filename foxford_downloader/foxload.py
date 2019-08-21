from itertools import chain
from multiprocessing import Pool, cpu_count

from lib.browser import terminate_browser_instance
from lib.fns import *
from lib.helpers import Logger, pipe
from lib.requests_cache import CachedSession


def download_course(email: str, password: str, course_name: str, actions: List[str]) -> None:
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

    selected_course: Dict = next(
        filter(
            lambda obj: f"({obj['grades_range']}) {obj['name']} - {obj['subtitle']}" == course_name,
            user_courses
        )
    )

    Logger.log("Fetching lesson list...")
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

    if "Resources" in actions:
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

        pool = Pool(cpu_count())
        pool.starmap(
            download_resources,
            map(
                lambda res_obj, path: [
                    {
                        **res_obj,
                        "destination": path
                    },
                    session
                ],
                resources_for_lessons,
                paths
            )
        )

        pool.close()
        pool.join()
        Logger.warn("Resources collection finished")

    coro_list = []
    semaphore = asyncio.Semaphore(2 if cpu_count() > 1 else 1)

    if "Homework" in actions:
        Logger.warn("Homework collection started")
        Logger.log("Collecting tasks...")

        lesson_tasks: Iterable[List[Dict]] = get_lesson_tasks(
            map(
                lambda obj: obj["id"],
                course_lessons_with_homework
            ),
            session
        )

        task_urls: Iterable[Iterable[str]] = construct_task_urls(
            map(
                lambda obj: obj["id"],
                course_lessons_with_homework
            ),
            lesson_tasks
        )

        paths: Iterable[Path] = build_dir_hierarchy(
            selected_course["name"],
            selected_course["subtitle"],
            selected_course["grades_range"],
            course_lessons_with_homework
        )

        Logger.warn(
            "Fetched tasks details. Homework collection will start soon..."
        )

        coro_list.extend(
            chain.from_iterable(
                map(
                    lambda url_tuple, path: map(
                        lambda url: save_page(
                            url,
                            path,
                            "homework",
                            map(
                                lambda item: {
                                    "name": item[0],
                                    "value": item[1],
                                    "domain": ".foxford.ru",
                                    "path": "/"
                                },
                                session.cookies.get_dict().items()
                            ),
                            semaphore
                        ),
                        url_tuple
                    ),
                    task_urls,
                    paths
                )
            )
        )

    if "Conspects" in actions:
        Logger.warn("Conspects collection started")

        conspect_urls: Iterable[Tuple[str]] = construct_conspect_urls(
            map(
                lambda obj: obj["id"],
                course_lessons_with_conspect
            ),
            map(
                lambda obj: obj["conspect_blocks_count"],
                course_lessons_with_conspect
            )
        )

        paths: Iterable[Path] = build_dir_hierarchy(
            selected_course["name"],
            selected_course["subtitle"],
            selected_course["grades_range"],
            course_lessons_with_conspect
        )

        Logger.warn(
            "Fetched conspects details. Conspects collection will start soon..."
        )

        coro_list.extend(
            chain.from_iterable(
                map(
                    lambda url_tuple, path: map(
                        lambda url: save_page(
                            url,
                            path,
                            "conspects",
                            map(
                                lambda item: {
                                    "name": item[0],
                                    "value": item[1],
                                    "domain": ".foxford.ru",
                                    "path": "/"
                                },
                                session.cookies.get_dict().items()
                            ),
                            semaphore
                        ),
                        url_tuple
                    ),
                    conspect_urls,
                    paths
                )
            )
        )

    if coro_list:
        Logger.warn("Actual collection started")

        asyncio.get_event_loop().run_until_complete(
            asyncio.wait(
                coro_list
            )
        )

        Logger.warn("Collection finished. Quitting...")
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.5))
        asyncio.get_event_loop().run_until_complete(terminate_browser_instance())
