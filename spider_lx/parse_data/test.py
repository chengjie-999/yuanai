from spider_lx.auto.web.selenium.selenium_cj import chrome


def test_go():
    driver = chrome()
    driver.get('')


if __name__ == '__main__':
    test_go()
