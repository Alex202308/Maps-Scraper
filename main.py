from multiprocessing import Process
import cities
import yandex_parser
import gis_parser

def main():
    search_query = 'Алкомаркет'
    processes = []

    # Запуск Яндекс парсера
    for city in cities.CITIES:
        p = Process(target=yandex_parser.parse_city_yandex, args=(city, search_query))
        p.start()
        processes.append(p)

    # Запуск 2ГИС парсера
    for city in cities.CITIES:
        p = Process(target=gis_parser.parse_city_2gis, args=(city, search_query))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    print("\n✓ Парсинг завершён для всех источников")

if __name__ == '__main__':
    main()
