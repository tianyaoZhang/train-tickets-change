#!/usr/bin/env python3
'''
基于 Python 3.x 的命令行版 12306 火车票查询器

Usage:
    train_tickets_cli.py (<from_city>) (<dest_city>) [<date>]

Example:
    python3 train_tickets_cli.py 成都 重庆 2019-10-24
'''

import os
import re
import json
import time
import requests
import colortext
from datetime import date
from docopt import docopt
from prettytable import PrettyTable

class TrainTicketsFinder():

    def __init__(self):
        # 解析命令行参数
        self.args = docopt(__doc__)
        # 指定 requests 响应编码
        self.response_encoding = 'utf-8'
        # 每次接口请求间隔时间限制，防止请求过快被返回异常
        self.request_interval_seconds = 5
        # 不支持的坐席类别用下面的符号表示
        self.unsupported_seat = colortext.light_yellow('×')
        # 获取并加载全国火车站站名信息
        self.fetch_all_station_names()
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
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.stations_json_file_cn_key = os.path.join(current_dir, 'stations_cn_key.json')
        self.stations_json_file_en_key = os.path.join(current_dir, 'stations_en_key.json')
        # 文件不存在就请求接口获取数据并写入文件
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
        # 文件存在就加载进内存
        self.stations_cn_key = json.load(open(self.stations_json_file_cn_key, 'rb'))
        self.stations_en_key = json.load(open(self.stations_json_file_en_key, 'rb'))
    
    def query_satisfied_trains_info(self):
        '''
        查询满足条件的车票信息，接口需要传递四个参数
        leftTicketDTO.train_date - 乘车日期，例如：2019-10-24，我这里做了一点优化处理，如果命令行不输日期参数，就默认查询当天
        leftTicketDTO.from_station - 出发车站，需要传车站的站名英文简写，我这里做了一点简化，只传出发的城市名称，接口也能够正确查询出车票信息
        leftTicketDTO.to_station - 到达车站，同出发车站做了一样的处理
        purpose_codes - 普通票或学生票，普通票传值为 ADULT
        '''
        from_city = self.args['<from_city>']
        dest_city = self.args['<dest_city>']
        # 检查输入的城市名是否正确
        if from_city not in self.stations_cn_key.keys():
            print(colortext.light_red('\n参数错误：出发城市 [%s] 不是一个正确的城市名' % from_city))
            return False
        
        if dest_city not in self.stations_cn_key.keys():
            print(colortext.light_red('\n参数错误：到达城市 [%s] 不是一个正确的城市名' % dest_city))
            return False

        # 检查输入的乘车日期是否正确
        train_date = self.args['<date>']
        today_date_str = str(date.today())
        train_date = train_date or today_date_str
        if train_date < today_date_str:
            print(colortext.light_yellow('\n参数错误：乘车日期 [%s] 不正确，将自动查询今天的车次信息' % train_date))
            train_date = today_date_str

        api = 'https://kyfw.12306.cn/otn/leftTicket/query'
        request_params = {
            'leftTicketDTO.train_date': train_date,
            'leftTicketDTO.from_station': self.stations_cn_key[from_city],
            'leftTicketDTO.to_station': self.stations_cn_key[dest_city],
            'purpose_codes': 'ADULT'
        }
        response = requests.get(api, params = request_params, cookies = self.cookie)

        if response.status_code == 200:
            trains_info = response.json().get('data').get('result')
            train_date = colortext.light_yellow(train_date)
            from_city = colortext.light_green(from_city)
            dest_city = colortext.light_red(dest_city)
            train_count = colortext.light_blue(len(trains_info))
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
                from_station = colortext.light_green(self.stations_en_key[train_info[6]])
                # 到达车站
                dest_station = colortext.light_red(self.stations_en_key[train_info[7]])
                station = from_station + '\n' + dest_station
                # 发车时间
                from_time = colortext.light_green(train_info[8])
                # 到达时间
                dest_time = colortext.light_red(train_info[9])
                time = from_time + '\n' + dest_time
                # 历时多久
                duration = train_info[10]
                # 余票及对应票价
                prices = self.query_train_prices(train_info, train_date = request_params['leftTicketDTO.train_date'])

                result_table.add_row([train_num, station, time, duration, prices['special_seat'], prices['first_seat'],
                    prices['second_seat'], prices['soft_sleep'], prices['hard_sleep'], prices['hard_seat'], prices['no_seat']
                ])

            print(result_table)

    def query_train_prices(self, train_info, train_date):
        '''查询各个坐席的票价'''

        # 查询票价需要用到的请求参数
        train_uuid = train_info[2]
        from_station_no = train_info[16]
        to_station_no = train_info[17]
        seat_types = train_info[35]

        api = 'https://kyfw.12306.cn/otn/leftTicket/queryTicketPrice'
        request_params = {
            'train_no': train_uuid,
            'from_station_no': from_station_no,
            'to_station_no': to_station_no,
            'seat_types': seat_types,
            'train_date': train_date
        }
        response = requests.get(api, params = request_params, cookies = self.cookie)

        prices = {
            'special_seat': train_info[32] or self.unsupported_seat, # 商务座/特等座余票
            'first_seat': train_info[31] or self.unsupported_seat,   # 一等座余票
            'second_seat': train_info[30] or self.unsupported_seat,  # 二等座余票
            'soft_sleep': train_info[23] or self.unsupported_seat,   # 软卧余票
            'hard_sleep': train_info[28] or self.unsupported_seat,   # 硬卧余票
            'hard_seat': train_info[29] or self.unsupported_seat,    # 硬座余票
            'no_seat': train_info[26] or self.unsupported_seat       # 站票余票
        }

        if response.status_code == 200:
            '''
            通过测试和观察，查询车票请求频率过快时会大概率导致请求失败，从而得到错误页面而不是正确的响应
            所以此处暂时以简单的方式做一个请求频率限制，每请求成功一次睡眠几秒钟，以此来规避请求异常问题
            '''
            print('编号为 %s 的列车票价请求成功，%d 秒后执行下一次车票查询请求' % (train_uuid, self.request_interval_seconds))
            time.sleep(self.request_interval_seconds)
            price_info = response.json().get('data')
            prices['special_seat'] += '\n' + colortext.light_yellow(price_info.get('A9', ''))
            prices['first_seat'] += '\n' + colortext.light_yellow(price_info.get('M', ''))
            prices['second_seat'] += '\n' + colortext.light_yellow(price_info.get('O', ''))
            prices['soft_sleep'] += '\n' + colortext.light_yellow(price_info.get('A4', ''))
            prices['hard_sleep'] += '\n' + colortext.light_yellow(price_info.get('A3', ''))
            prices['hard_seat'] += '\n' + colortext.light_yellow(price_info.get('A1', ''))
            # 站票票价先匹配普通列车，等于硬座票价，如果匹配不到，那么就等于二等座的票价
            prices['no_seat'] += '\n' + colortext.light_yellow(price_info.get('A1', price_info.get('WZ', '')))

        return prices


if __name__ == '__main__':
    app = TrainTicketsFinder()
    app.query_satisfied_trains_info()
