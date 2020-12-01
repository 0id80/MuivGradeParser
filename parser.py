from re import search, findall
from typing import Union

from exceptions import FailedAuth

from requests import post, get
from bs4 import BeautifulSoup

# # Config ---------------------------------------------------------------------------------------------------------------
# from Config import config_ini, account_ini
#
# DEV = config_ini("dev_config", "project", "dev")
DEV = True
# ----------------------------------------------------------------------------------------------------------------------


class UserGrade:
    def __init__(self, login, password):
        self.login: str = login
        self.password: str = password
        self.url = "https://e.muiv.ru/login/index.php"

    # Get all html data
    def get_html(self):
        form = get(self.url)
        token = search(r'logintoken" value="\S+"', form.text).group().split('"')[2]
        login_information = {'username': self.login,
                             'password': self.password,
                             'rememberusername': 1,
                             'anchor': None,
                             'logintoken': token}
        data = post(self.url, data=login_information, cookies=form.cookies)
        html = data.content
        soup = BeautifulSoup(html, 'lxml')
        return soup

    # Accepts raw html -> Returns a list 0: student Name 1: not filtered list for all courses
    def get_courses_div(self):
        """
        Set data = self.__get_test_html() - to do test in your test.html
        """
        if DEV:
            data = self.__get_test_html()
        else:
            data = self.get_html()

        try:
            student_name: str = data.find("span", class_="usertext").text
            div_courses: list = data.find_all('div', class_='dis_block')
            return student_name, div_courses
        except AttributeError:
            raise FailedAuth("Invalid username or password, please try again.")

    def get_json(self):
        """
        Returns a ready-made dictionary in json format with all the data
        """
        def _get(grades_list: Union[list, tuple], index: int, default=0):
            """
            Checking the content of tests in the discipline
            If there is a test -> returns the test score, otherwise 0
            """
            try:
                return grades_list[index]
            except IndexError:
                return default

        def _get_done_course(data: dict) -> int:
            done = int()
            for course in data["courses"]:
                if 0 not in data["courses"][course].values():
                    done += 1
            return done

        def _get_test_count(data: dict) -> int:
            count = int()
            for course in data["courses"]:
                for test in data["courses"][course]:
                    if test.startswith("Тест"):
                        count += 1
            return count

        def _get_test_done(data: dict) -> int:
            done = int()
            for course in data["courses"]:
                for test in data["courses"][course]:
                    if test.startswith("Тест") and data["courses"][course][test] != 0:
                        done += 1
            return done

        def minimum_test_value(grades):
            """
            Returns the value of X up to the minimum average score of 75
            """
            sort_grade = sorted(grades)
            sort_grade.pop(0)
            min_value = (75 - (sum(sort_grade) / len(grades))) * len(grades)
            if min_value > sorted(grades)[0]:
                return min_value - sorted(grades)[0]

            else:
                return "Не требуется. Средний балл >75"

        def minimum_test_value_excellent(grades):
            """
            Returns the value of X up to the minimum average score of 85
            """
            sort_grade = sorted(grades)
            sort_grade.pop(0)
            min_value = (85 - (sum(sort_grade) / len(grades))) * len(grades)
            if min_value > sorted(grades)[0]:
                return min_value - sorted(grades)[0]

            else:
                return "Не требуется. Средний балл >85"

        student_name, div_courses = self.get_courses_div()
        out_data = dict()

        def find_teacher(course):
            try:
                return course.find("span", class_="teachers").text
            except:
                return ""

        out_data["user"] = {key: value for key, value in zip(["surname", "name", "patronymic"], student_name.split())}
        out_data["courses"] = dict()

        for course in div_courses:
            course_header = {"type": course.find('span', class_='reports').text,
                             "teacher": find_teacher(course)}
            test_names = findall(r"Тест\s\d",  str(course))
            if len(test_names):
                test_grades = tuple(map(lambda grade: int(grade) if grade.isdigit() else 0, findall(r">( \/ не выполнено|\d+)<", str(course))))
                course_tests = {test_name: _get(test_grades, index) for index, test_name in enumerate(findall(r"Тест\s\d", str(course)))}
                course_tests["middle"] = round(sum(course_tests.values()) / len(course_tests), 2)
                course_tests["minimum_test_value"] = minimum_test_value(test_grades)
                course_tests["minimum_test_value_excellent"] = minimum_test_value_excellent(test_grades)
                out_data["courses"][course.find('span', class_='dis_name').text.strip(' 1234567890.')] = dict(**course_header, **course_tests)
            else:
                out_data["courses"][course.find('span', class_='dis_name').text.strip(' 1234567890.')] = course_header

        course_done = _get_done_course(out_data)
        test_count = _get_test_count(out_data)
        test_done = _get_test_done(out_data)
        out_data["progress"] = {"course_count": len(out_data["courses"]),
                                "course_done": course_done,
                                "course_remained": len(out_data["courses"]) - course_done,
                                "test_count": test_count,
                                "test_done": test_done,
                                "test_remained": test_count - test_done,
                                "test_percentage_done": int((test_done/test_count) * 100),
                                }
        return out_data

    # Normal out in console --------------------------------------------------------------------------------------------
    def print(self):
        json = self.get_json()
        print("ФИО:", " ".join(list(json["user"].values())))
        print()
        for course in json["courses"]:
            print(course, "|", json["courses"][course]["type"])
            for test in json["courses"][course]:
                if test.startswith("Тест"):
                    print(test, ":", json["courses"][course][test])
            if json["courses"][course].get("middle") is not None:
                print("Средний балл:", json["courses"][course].get("middle"))
            else:
                print("У данной дисциплины нет тестов")
            print(json["courses"][course]["teacher"])
            print()
        print("Кол-во предметов:", json["progress"]["course_count"], "|",
              "Кол-во полностью закрытых предметов:", json["progress"]["course_done"], "|",
              "Кол-во не закрытых предметов:", json["progress"]["course_remained"])
        print("Кол-во тестов:", json["progress"]["test_count"], "|",
              "Кол-во решеных тестов:", json["progress"]["test_done"], "|",
              "Кол-во не решеных тестов:", json["progress"]["test_remained"])

        return "Finished!"

    # TO SAVE THE HTML PAGE TO MAKE THE TEST REQUEST -------------------------------------------------------------------
    def save_html(self):
        html = self.get_html()
        with open('test.html', "w", encoding="UTF-8") as file:
            file.seek(0)
            file.write(str(html))

    # TEST ZONE --------------------------------------------------------------------------------------------------------

    # Function for testing all methods on test information of courses
    @staticmethod
    def __get_test_html():
        """
        test.html -> page "https://e.muiv.ru/my/"
        """
        with open("test.html", encoding="utf-8") as file:
            html = file.read()
        return BeautifulSoup(html, "html.parser")
    # ------------------------------------------------------------------------------------------------------------------


# TEST Launch ----------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    """
    The "Accounts Data" variable is optional. it is needed to get data about accounts from .json file
    Creating a "UserGrade" object:
        variable_name = UserGrade("LOGIN", "PASSWORD")
    """
    try:

        Evgeniy = UserGrade("login", "password")
        print(Evgeniy.print())

    except FailedAuth as err:
        print(err.__str__())
