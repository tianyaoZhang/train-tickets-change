"""
基于 Python 3.7 的命令行版 12306 火车票查询器

Usage:
    train_tickets_cli.py (<from_city>) (<dest_city>) [<date>]

Example:
    python3 train_tickets_cli.py 成都 重庆 2019-10-24
"""

import os
import re
import json
import requests
import datetime
from docopt import docopt
from colorama import Fore, Style
from prettytable import PrettyTable

class TrainTicketsFinder():

    def __init__(self):
        self.args = docopt(__doc__)
        self.response_encoding = 'utf-8'
        self.stations_json_file_cn_key = 'stations_cn_key.json'
        self.stations_json_file_en_key = 'stations_en_key.json'
        self.fetch_all_station_names()
        self.stations_cn_key = json.load(open(self.stations_json_file_cn_key, 'r'))
        self.stations_en_key = json.load(open(self.stations_json_file_en_key, 'r'))

        self.try_fetching_cookie()

    def try_fetching_cookie(self):
        response = requests.get('https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc')
        if response.status_code == 200: self.cookie = response.cookies

    def fetch_all_station_names(self):
        if not os.path.exists(self.stations_json_file_cn_key):
            data = requests.get('https://www.12306.cn/index/script/core/common/station_name_v10042.js')
            data.encoding = self.response_encoding

            if data.status_code == 200:
                stations = re.findall(r'([\u4e00-\u9fa5]+)\|([A-Z]+)', data.text)
                stations_dict_cn_key = dict(stations)
                stations_json_file_cn_key = open(self.stations_json_file_cn_key, 'w')
                json.dump(stations_dict_cn_key, stations_json_file_cn_key, ensure_ascii = False)
                stations_json_file_en_key = open(self.stations_json_file_en_key, 'w')
                stations_dict_en_key = dict(zip(stations_dict_cn_key.values(), stations_dict_cn_key.keys()))
                json.dump(stations_dict_en_key, stations_json_file_en_key, ensure_ascii = False)
    
    def query_satisfied_trains_info(self):
        api = 'https://kyfw.12306.cn/otn/leftTicket/query'
        request_params = {
            'leftTicketDTO.train_date': datetime.date.today() if self.args['<date>'] == None else self.args['<date>'],
            'leftTicketDTO.from_station': self.stations_cn_key[self.args['<from_city>']],
            'leftTicketDTO.to_station': self.stations_cn_key[self.args['<dest_city>']],
            'purpose_codes': 'ADULT'
        }
        response = requests.get(api, params = request_params, cookies = self.cookie)

        if response.status_code == 200:
            response_json = response.json()
            trains_info = response_json['data']['result']
            train_date = Fore.YELLOW + str(request_params['leftTicketDTO.train_date']) + Style.RESET_ALL
            from_city = Fore.GREEN + self.args['<from_city>'] + Style.RESET_ALL
            dest_city = Fore.RED + self.args['<dest_city>'] + Style.RESET_ALL
            train_count = Fore.BLUE + str(len(trains_info)) + Style.RESET_ALL
            print('\n查询到 %s 从 %s 到 %s 的列车一共 %s 趟\n' % (train_date, from_city, dest_city, train_count))

            result_table = PrettyTable()
            result_table.field_names = ['车次', '车站', '时间', '历时', '商务座/特等座', '一等座', '二等座', '软卧', '硬卧', '硬座', '站票']

            for train in trains_info:
                train_info = train.split('|')
                train_num = train_info[3]
                from_station = Fore.GREEN + self.stations_en_key[train_info[6]] + Style.RESET_ALL
                dest_station = Fore.RED + self.stations_en_key[train_info[7]] + Style.RESET_ALL
                station = from_station + '\n' + dest_station
                from_time = Fore.GREEN + train_info[8] + Style.RESET_ALL
                dest_time = Fore.RED + train_info[9] + Style.RESET_ALL
                time = from_time + '\n' + dest_time
                duration = train_info[10]
                special_seat = train_info[32]
                first_seat = train_info[31]
                second_seat = train_info[30]
                soft_sleep = train_info[23]
                hard_sleep = train_info[28]
                hard_seat = train_info[29]
                no_seat = train_info[26]

                result_table.add_row([
                    train_num, station, time, duration, special_seat, first_seat,
                    second_seat, soft_sleep, hard_sleep, hard_seat, no_seat
                ])
            print(result_table)

if __name__ == '__main__':
    app = TrainTicketsFinder()
    app.query_satisfied_trains_info()