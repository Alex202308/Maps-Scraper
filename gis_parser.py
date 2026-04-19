from time import sleep
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
from datetime import datetime

import pathes_2gis as pathes
import iuliia


TABLE_COLUMNS = ['Город', 'Название магазина', 'Адрес', 'Рейтинг']

def get_element_text(driver: WebDriver, path: str) -> str:
    try:
        return driver.find_element(By.XPATH, path).text
    except NoSuchElementException:
        return ''

def element_click(driver: WebDriver | WebElement, path: str) -> bool:
    try:
        driver.find_element(By.XPATH, path).click()
        return True
    except:
        return False
    
def slugify_city(city_name: str) -> str:
    """Преобразует русское название города в транслит для URL"""
    # Транслитерация по схеме Яндекс.Карт
    transliterated = iuliia.translate(city_name, schema=iuliia.YANDEX_MAPS)
    # Приводим к нижнему регистру и заменяем пробелы на дефисы
    return transliterated.lower().replace(" ", "-")


def parse_city_2gis(city: str, search_query: str = 'Алкомаркеты'):
    TABLE = {column: [] for column in TABLE_COLUMNS}
    city_slug = slugify_city(city)
    url = f'https://2gis.ru/{city_slug}/search/{search_query}'
    driver = webdriver.Chrome()
    driver.maximize_window()
    driver.get(url)
    wait = WebDriverWait(driver, 10)

    try:
        cookie_btn = wait.until(EC.element_to_be_clickable((By.XPATH, pathes.cookie_banner)))
        cookie_btn.click()
    except:
        pass

    count_all_items = int(get_element_text(driver, pathes.items_count))
    pages = round(count_all_items / 12 + 0.5)
    processed = 0
    saved = 0
    print(f"[2GIS][{city}] Начало парсинга: {count_all_items} позиций, {pages} страниц")

    for page_num in range(1, pages + 1):
        try:
            main_block = wait.until(EC.presence_of_element_located((By.XPATH, pathes.main_block)))
        except:
            print(f"[2GIS][{city}] Не найден блок с карточками")
            break

        count_items = len(main_block.find_elements(By.XPATH, './div'))
        print(f"[2GIS][{city}] Страница {page_num}: {count_items} карточек")

        for item_idx in range(1, count_items + 1):
            try:
                card_xpath = f'./div[{item_idx}]/div/div[2]'
                card = main_block.find_element(By.XPATH, card_xpath)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                card.click()
                sleep(0.8)

                title = get_element_text(driver, pathes.title)
                address = get_element_text(driver, pathes.address_variant_1) or get_element_text(driver, pathes.address_variant_2)
                rating = ''
                try:
                    

                    # Ищем кнопку "Отзывы" и кликаем
                    review_btn = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, pathes.review_btn))
                    )

                    # Кликаем через JavaScript, чтобы избежать перехвата
                    driver.execute_script("arguments[0].click();", review_btn)
                    

                    # Проверяем, не появилось ли окно с новостями (кнопка "Хорошо")
                    try:
                        agree_btn = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, pathes.agree_btn))
                        )
                        agree_btn.click()
                        
                    except TimeoutException:
                        pass  # окна не было, идём дальше
                    # Извлекаем рейтинг
                    rating = get_element_text(driver, pathes.rating_v1) or get_element_text(driver, pathes.rating_v2)
                except (NoSuchElementException, TimeoutException):
                    # Если вкладки нет или рейтинг не найден, оставляем пустым
                    pass

                processed += 1
                if title and address:
                    TABLE['Город'].append(city)
                    TABLE['Название магазина'].append(title)
                    TABLE['Адрес'].append(address)
                    TABLE['Рейтинг'].append(rating)
                    saved += 1
            except StaleElementReferenceException:
                continue
            except Exception as e:
                print(f"Ошибка в карточке {item_idx}: {e}")
                continue

        if page_num < pages:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            next_clicked = element_click(driver, pathes.next_page)
            if not next_clicked:
                print(f"[2GIS][{city}] Не удалось перейти на следующую страницу")
                break
            sleep(1.5)

    print(f"[2GIS][{city}] ✓ Обработано: {processed} | Сохранено: {saved}")
    driver.quit()

    save_folder = os.path.join(city, "2gis")
    os.makedirs(save_folder, exist_ok=True)
    base_filename = f"{city}_{search_query}_2gis"
    filename = f"{base_filename}.xlsx"
    filepath = os.path.join(save_folder, filename)

    if os.path.exists(filepath):
        timestamp = datetime.now().strftime("%H-%M-%d-%m-%y")
        filename = f"{base_filename}-{timestamp}.xlsx"
        filepath = os.path.join(save_folder, filename)

    pd.DataFrame(TABLE).to_excel(filepath, index=False)
    print(f"[2GIS][{city}] Данные сохранены в {filepath}")