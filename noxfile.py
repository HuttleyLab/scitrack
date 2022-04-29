import nox

dependencies = "numpy", "click", "pytest", "pytest-cov"


@nox.session(python=[f"3.{v}" for v in range(7, 11)])
def test(session):
    py_version = session.python.replace(".", "")
    session.install(*dependencies)
    session.install(".")
    session.chdir("tests")
    session.run(
        "pytest",
        "-x",
        "--junitxml",
        f"junit-{py_version}.xml",
        "--cov-report",
        "xml",
        "--cov",
        "scitrack",
    )
