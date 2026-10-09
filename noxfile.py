import nox

py_vers = [f"3.{v}" for v in range(11, 16)]
free_threaded_vers = ["3.14t", "3.15t"]


@nox.session(python=py_vers[-1], venv_backend="uv")
def fmt(session: nox.Session) -> None:
    session.install("-e", ".", "--group", "dev")
    session.run("ruff", "check", "--fix-only", ".")
    session.run("ruff", "format", ".")


@nox.session(python=py_vers, venv_backend="uv")
def type_check(session):
    session.install("-e", ".", "--group", "dev")
    session.run("mypy", "src/scitrack/")


@nox.session(python=[*py_vers, *free_threaded_vers], venv_backend="uv")
def test(session):
    session.install("-e", ".", "--group", "dev")
    session.chdir("tests")
    session.run(
        "pytest",
        "-s",
        "-x",
        *session.posargs,
    )


@nox.session(python=[*py_vers, *free_threaded_vers], venv_backend="uv")
def testcov(session):
    session.install("-e", ".", "--group", "dev")
    session.run(
        "pytest",
        "--cov-report",
        "html",
        "--cov",
        "scitrack",
        ".",
        *session.posargs,
    )
