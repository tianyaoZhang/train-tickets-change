#!/usr/bin/env python3
'''
基于 Python 3.7 的命令行版 12306 火车票查询器

Usage:
    train_tickets_cli.py (<from_city>) (<dest_city>) [<date>]

Example:
    python3 train_tickets_cli.py 成都 重庆 2019-10-24
'''

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
        # 解析命令行参数
        self.args = docopt(__doc__)
        # 指定 requests 响应编码
        self.response_encoding = 'utf-8'
        # 不支持的坐席类别用下面的符号表示
        self.unsupported_seat = Fore.YELLOW + '×' + Style.RESET_ALL
        # 获取并加载全国火车站站名信息
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.stations_json_file_cn_key = os.path.join(current_dir, 'stations_cn_key.json')
        self.stations_json_file_en_key = os.path.join(current_dir, 'stations_en_key.json')
        self.fetch_all_station_names()
        self.stations_cn_key = json.load(open(self.stations_json_file_cn_key, 'rb'))
        self.stations_en_key = json.load(open(self.stations_json_file_en_key, 'rb'))
        # 尝试获取 12306 网站 cookie
        self.try_fetching_cookie()

    def try_fetching_cookie(self):
        '''通过下面链接获取网站 cookie，为后面的查询车票请求做准备'''
        response = requests.get('https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc')
        if response.status_code == 200: self.cookie = response.cookies

    def fetch_all_station_names(self):
        '''
        获取全国火车站站名信息，在 12306 网站上是以下面的 JavaScript 链接直接写死了返回来的
        查询车票请求主要需要用到里面的中文站名以及站名的英文简写，函数中将它们整理成一个字典，并最终存成 json 文件
        stations_cn_key.json 用于查询车票时，命令行输入出发城市和到达城市中文名，然后匹配对应的站名英文简写发请求
        stations_en_key.json 用于处理查询响应，接口返回的是站名英文简写，要在结果中显示出中文站名，就需要再做匹配
        '''
        if not os.path.exists(self.stations_json_file_cn_key):
            data = requests.get('https://www.12306.cn/index/script/core/common/station_name_v10042.js')
            data.encoding = self.response_encoding

            if data.status_code == 200:
                stations = re.findall(r'([\u4e00-\u9fa5]+)\|([A-Z]+)', data.text)
                stations_dict_cn_key = dict(stations)
                stations_json_file_cn_key = open(self.stations_json_file_cn_key, 'w', encoding = data.encoding)
                json.dump(stations_dict_cn_key, stations_json_file_cn_key, ensure_ascii = False)
                stations_json_file_en_key = open(self.stations_json_file_en_key, 'w', encoding = data.encoding)
                stations_dict_en_key = dict(zip(stations_dict_cn_key.values(), stations_dict_cn_key.keys()))
                json.dump(stations_dict_en_key, stations_json_file_en_key, ensure_ascii = False)
    
    def query_satisfied_trains_info(self):
        '''
        查询满足条件的车票信息，接口需要传递四个参数
        leftTicketDTO.train_date - 乘车日期，例如：2019-10-24，我这里做了一点优化处理，如果命令行不输日期参数，就默认查询当天
        leftTicketDTO.from_station - 出发车站，需要传车站的站名英文简写，我这里做了一点简化，只传出发的城市名称，接口也能够正确查询出车票信息
        leftTicketDTO.to_station - 到达车站，同出发车站做了一样的处理
        purpose_codes - 普通票或学生票，普通票传值为 ADULT
        '''
        # 检查输入的城市名是否正确
        if self.args['<from_city>'] not in self.stations_cn_key.keys():
            print(Fore.RED + '\n参数错误：出发城市 [%s] 不是一个正确的城市名' % self.args['<from_city>'] + Style.RESET_ALL)
            return False
        
        if self.args['<dest_city>'] not in self.stations_cn_key.keys():
            print(Fore.RED + '\n参数错误：到达城市 [%s] 不是一个正确的城市名' % self.args['<dest_city>'] + Style.RESET_ALL)
            return False

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

            # 遍历查询到的全部车次信息
            for train in trains_info:
                '''
                按 12306 现有的接口，返回的数据是一个列表，单条数据是以 | 分隔的字符串
                在分析这里的数据时，我是靠规律和基本猜测确定对应数据在哪个字段上的
                不知道官方接口为什么要这样返回数据，防止爬虫？感觉这样也防不住啊！
                '''
                train_info = train.split('|')
                # 车次
                train_num = train_info[3]
                # 出发车站
                from_station = Fore.GREEN + self.stations_en_key[train_info[6]] + Style.RESET_ALL
                # 到达车站
                dest_station = Fore.RED + self.stations_en_key[train_info[7]] + Style.RESET_ALL
                station = from_station + '\n' + dest_station
                # 发车时间
                from_time = Fore.GREEN + train_info[8] + Style.RESET_ALL
                # 到达时间
                dest_time = Fore.RED + train_info[9] + Style.RESET_ALL
                time = from_time + '\n' + dest_time
                # 历时多久
                duration = train_info[10]
                # 商务座/特等座余票
                special_seat = train_info[32]
                # 一等座余票
                first_seat = train_info[31]
                # 二等座余票
                second_seat = train_info[30]
                # 软卧余票
                soft_sleep = train_info[23]
                # 硬卧余票
                hard_sleep = train_info[28]
                # 硬座余票
                hard_seat = train_info[29]
                # 站票余票
                no_seat = train_info[26]

                result_table.add_row([
                    train_num, station, time, duration, special_seat or self.unsupported_seat,
                    first_seat or self.unsupported_seat, second_seat or self.unsupported_seat,
                    soft_sleep or self.unsupported_seat, hard_sleep or self.unsupported_seat,
                    hard_seat or self.unsupported_seat, no_seat or self.unsupported_seat
                ])

            print(result_table)


if __name__ == '__main__':
    app = TrainTicketsFinder()
    app.query_satisfied_trains_info()