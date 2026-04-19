from time import sleep
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
from datetime import datetime

import pathes_yandex as pathes

TABLE_COLUMNS = ['Город', 'Название магазина', 'Адрес', 'Рейтинг']

def get_element_text(parent, path: str) -> str:
    try:
        return parent.find_element(By.XPATH, path).text
    except NoSuchElementException:
        return ''

def get_address(item):
    try:
        addr_elem = item.find_element(By.XPATH, pathes.address)
        return addr_elem.text.strip()
    except NoSuchElementException:
        return ''

def parse_city_yandex(city: str, search_query: str = 'Магазины алкоголя'):
    TABLE = {column: [] for column in TABLE_COLUMNS}
    url = 'https://yandex.ru/maps/'
    driver = webdriver.Chrome()
    driver.maximize_window()
    driver.get(url)
    sleep(3)
    wait = WebDriverWait(driver, 15)

    print(f"[Yandex][{city}] Старт парсинга")

    full_query = f"{search_query} {city}"
    for attempt in range(3):
        try:
            search_input = driver.find_element(By.XPATH, pathes.search_input)
            search_input.clear()
            search_input.send_keys(full_query)
            print(f"[Yandex][{city}] Введён запрос: '{full_query}'")
            break
        except StaleElementReferenceException:
            if attempt == 2:
                raise
            sleep(1)

    for attempt in range(3):
        try:
            button = driver.find_element(By.XPATH, pathes.search_button)
            button.click()
            print(f"[Yandex][{city}] Поиск запущен")
            break
        except StaleElementReferenceException:
            if attempt == 2:
                raise
            sleep(1)

    try:
        wait.until(EC.presence_of_element_located((By.XPATH, pathes.first_item)))
        print(f"[Yandex][{city}] Результаты загружены")
    except TimeoutException:
        print("❌ Нет результатов поиска")
        driver.quit()
        return

    try:
        scroll_block = wait.until(EC.presence_of_element_located((By.XPATH, pathes.scroll_container)))
    except TimeoutException:
        print("❌ Не найден scroll контейнер")
        driver.quit()
        return

    last_count = 0
    same_count = 0

    while True:
        items = scroll_block.find_elements(By.XPATH, pathes.items)
        current_count = len(items)
        print(f"[Yandex][{city}] Карточек: {current_count}")

        if current_count == last_count:
            same_count += 1
        else:
            same_count = 0

        if same_count >= 5:
            print(f"[Yandex][{city}] Скролл завершён")
            break

        last_count = current_count

        for _ in range(6):
            driver.execute_script("arguments[0].scrollTop += 300", scroll_block)
            sleep(0.4)
        sleep(1.5)

    processed = 0
    saved = 0
    items = scroll_block.find_elements(By.XPATH, pathes.items)

    for item in items:
        try:
            title = get_element_text(item, pathes.title)
            address = get_address(item)
            rating = get_element_text(item, pathes.rating)
            processed += 1
            if title:
                TABLE['Город'].append(city)
                TABLE['Название магазина'].append(title)
                TABLE['Адрес'].append(address)
                TABLE['Рейтинг'].append(rating)
                saved += 1
        except StaleElementReferenceException:
            continue

    print(f"[Yandex][{city}] ✓ Обработано: {processed} | Сохранено: {saved}")
    driver.quit()

    # Сохранение в папку yandex внутри города
    save_folder = os.path.join(city, "yandex")
    os.makedirs(save_folder, exist_ok=True)
    base_filename = f"{city}_{search_query}_yandex"
    filename = f"{base_filename}.xlsx"
    filepath = os.path.join(save_folder, filename)

    if os.path.exists(filepath):
        timestamp = datetime.now().strftime("%H-%M-%d-%m-%y")
        filename = f"{base_filename}-{timestamp}.xlsx"
        filepath = os.path.join(save_folder, filename)

    pd.DataFrame(TABLE).to_excel(filepath, index=False)
    print(f"[Yandex][{city}] Данные сохранены в {filepath}")