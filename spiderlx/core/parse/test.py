from spiderlx.auto.web.selenium.main import chrome


def test_go():
    driver = chrome()
    driver.get('')


if __name__ == '__main__':
    test_go()
