import pandas as pd
import os
import re
from pathlib import Path
from datetime import datetime
from fuzzywuzzy import fuzz

import cities

def normalize_name(name):
    if pd.isna(name) or not isinstance(name, str):
        return ""
    name = name.lower().strip()
    name = name.replace('ё', 'е')
    # удаляем все не буквы/цифры/пробелы
    name = re.sub(r'[^\w\s]', '', name)
    # убираем лишние пробелы
    return re.sub(r'\s+', ' ', name).strip()

def extract_address_key(addr):
    """
    Извлекает ключевую часть адреса: улица и номер дома.
    Пример: "ул. Ленина, д. 10, кв. 5" -> "ленина 10"
    """
    if pd.isna(addr) or not isinstance(addr, str):
        return ""
    addr = addr.lower().strip()
    # Удаляем всё после запятой, "район", "округ", "этаж" и т.п.
    addr = re.split(r',|\(|\)|район|округ|этаж|помещение|офис|кв\.|квартира|корпус|литера|строение|сочи|краснодарский край', addr)[0]
    # Убираем типовые слова: ул, улица, пр-т, проспект и т.д.
    addr = re.sub(r'\b(ул|улица|пр-т|проспект|пер|переулок|бул|бульвар|шоссе|наб|набережная|пл|площадь|пр|прт|бвр|ш|д|дом)\.?\s*', '', addr)
    # Убираем знаки препинания и лишние пробелы
    addr = re.sub(r'[^\w\s]', ' ', addr)
    addr = re.sub(r'\s+', ' ', addr).strip()
    return addr

def safe_rating_to_numeric(rating):
    if pd.isna(rating) or rating == '':
        return None
    if isinstance(rating, str):
        # Если рейтинг содержит "Реклама" — считаем его отсутствующим
        if 'реклама' in rating.lower():
            return None
        rating = rating.replace(',', '.')
        match = re.search(r'(\d+\.?\d*)', rating)
        if match:
            rating = match.group(1)
        else:
            return None
    try:
        return float(rating)
    except ValueError:
        return None

def merge_city(city):
    yandex_folder = Path(city) / "yandex"
    gis_folder = Path(city) / "2gis"
    merged_folder = Path("merged") / city
    merged_folder.mkdir(parents=True, exist_ok=True)

    y_files = sorted(
        [f for f in yandex_folder.glob("*.xlsx") if not f.name.startswith("~$")],
        key=os.path.getmtime,
        reverse=True
    )
    g_files = sorted(
        [f for f in gis_folder.glob("*.xlsx") if not f.name.startswith("~$")],
        key=os.path.getmtime,
        reverse=True
    )

    if not y_files or not g_files:
        print(f"[{city}] Отсутствуют данные для слияния")
        return

    df_y = pd.read_excel(y_files[0])
    df_g = pd.read_excel(g_files[0])

    # Подготовка данных
    df_y['Рейтинг_числ'] = df_y['Рейтинг'].apply(safe_rating_to_numeric)
    df_g['Рейтинг_числ'] = df_g['Рейтинг'].apply(safe_rating_to_numeric)

    df_y['name_norm'] = df_y['Название магазина'].apply(normalize_name)
    df_g['name_norm'] = df_g['Название магазина'].apply(normalize_name)

    df_y['addr_key'] = df_y['Адрес'].apply(extract_address_key)
    df_g['addr_key'] = df_g['Адрес'].apply(extract_address_key)

    # Дедупликация внутри источников по name_norm + addr_key
    def deduplicate(df, source_name):
        before = len(df)
        # Оставляем первое вхождение, но можно было бы агрегировать рейтинг (max)
        df.drop_duplicates(subset=['name_norm', 'addr_key'], keep='first', inplace=True)
        print(f"[{city}] Дедупликация {source_name}: было {before}, стало {len(df)}")
        return df

    df_y = deduplicate(df_y, "Yandex")
    df_g = deduplicate(df_g, "2GIS")

    merged_rows = []
    used_g_indices = set()

    # Сначала сопоставляем магазины с одинаковым нормализованным названием
    for idx_y, row_y in df_y.iterrows():
        name_y = row_y['name_norm']
        addr_key_y = row_y['addr_key']

        # Кандидаты из 2GIS с таким же названием
        candidates = df_g[df_g['name_norm'] == name_y]
        best_score = 0
        best_match = None
        best_idx_g = None

        for idx_g, row_g in candidates.iterrows():
            if idx_g in used_g_indices:
                continue
            addr_key_g = row_g['addr_key']
            # Сравниваем адресные ключи
            score = fuzz.token_sort_ratio(addr_key_y, addr_key_g)
            # Если один ключ содержит другой, повышаем уверенность
            if addr_key_y and addr_key_g:
                if addr_key_y in addr_key_g or addr_key_g in addr_key_y:
                    score = max(score, 90)
            if score > best_score:
                best_score = score
                best_match = row_g
                best_idx_g = idx_g

        # Порог для адресного совпадения
        if best_match is not None and best_score >= 85:
            used_g_indices.add(best_idx_g)
            rating_y = row_y['Рейтинг_числ']
            rating_g = best_match['Рейтинг_числ']
            ratings = [r for r in (rating_y, rating_g) if pd.notna(r)]
            avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

            merged_rows.append({
                'Город': city,
                'Название магазина': row_y['Название магазина'],
                'Адрес': row_y['Адрес'],
                'Рейтинг Яндекс': row_y['Рейтинг'],
                'Рейтинг 2Gis': best_match['Рейтинг'],
                'Средний Рейтинг': avg_rating
            })
        else:
            merged_rows.append({
                'Город': city,
                'Название магазина': row_y['Название магазина'],
                'Адрес': row_y['Адрес'],
                'Рейтинг Яндекс': row_y['Рейтинг'],
                'Рейтинг 2Gis': None,
                'Средний Рейтинг': row_y['Рейтинг_числ']
            })

    # Добавляем оставшиеся из 2GIS
    for idx_g, row_g in df_g.iterrows():
        if idx_g not in used_g_indices:
            merged_rows.append({
                'Город': city,
                'Название магазина': row_g['Название магазина'],
                'Адрес': row_g['Адрес'],
                'Рейтинг Яндекс': None,
                'Рейтинг 2Gis': row_g['Рейтинг'],
                'Средний Рейтинг': row_g['Рейтинг_числ']
            })

    df_merged = pd.DataFrame(merged_rows)
    timestamp = datetime.now().strftime("%H-%M-%d-%m-%y")
    output_file = merged_folder / f"{city}_yandex_2gis_merged_{timestamp}.xlsx"
    df_merged.to_excel(output_file, index=False)
    print(f"[{city}] Объединённый файл сохранён: {output_file}\n")

def main():
    for city in cities.CITIES:
        merge_city(city)
    print("✓ Слияние завершено")

if __name__ == '__main__':
    main()