#!/usr/bin/env python3
"""
基于 Python 3.x 的命令行版 12306 火车票查询器

Usage:
    app.py (<from_city>) (<dest_city>) [<date>] [-g][-c][-d][-k][-t][-z][-l]
"""

import re
import sys
import time
from datetime import date
from json import JSONDecodeError

import requests
from docopt import docopt
from prettytable import PrettyTable

import colortext
from mysqlite import Sqlite


class TrainTicketsFinder:

    def __init__(self):
        # 解析命令行参数
        self.args = docopt(__doc__)
        # 指定 requests 响应编码
        self.response_encoding = 'utf-8'
        # 每次接口请求间隔时间限制，防止请求过快被返回异常
        self.request_interval_seconds = 5
        # 不支持的坐席类别用下面的符号表示
        self.unsupported_seat = colortext.light_yellow('×')
        # 初始化数据库并创建数据表
        self.db = Sqlite('data.sqlite3')
        # 获取并加载全国火车站站名信息
        self.fetch_all_station_names()
        # 尝试获取 12306 网站 cookie
        self.cookies = requests.get('https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc').cookies

    def fetch_all_station_names(self):
        """获取全国火车站站名信息，在 12306 网站上是以下面的 JavaScript 链接直接写死了返回来的"""
        if self.db.select_one_from(self.db.table_name_station) is None:
            response = requests.get('https://www.12306.cn/index/script/core/common/station_name_v10042.js')
            response.encoding = self.response_encoding
            if response.ok:
                stations = re.findall(r'([\u4e00-\u9fa5]+)\|([A-Z]+)\|([a-z]+)\|([a-z]+)', response.text)
                self.db.batch_insert_stations_data(stations)

    def query_satisfied_trains_info(self):
        """
        查询满足条件的车票信息，接口需要传递四个参数
        leftTicketDTO.train_date - 乘车日期，例如：2019-10-24，我这里做了一点优化处理，如果命令行不输日期参数，就默认查询当天
        leftTicketDTO.from_station - 出发车站，需要传车站的站名英文简写，我这里做了一点简化，只传出发的城市名称，接口也能够正确查询出车票信息
        leftTicketDTO.to_station - 到达车站，同出发车站做了一样的处理
        purpose_codes - 普通票或学生票，普通票传值为 ADULT
        """
        from_city, dest_city, from_station_en, dest_station_en, train_date, need_filter = self._check_input_args()
        api = 'https://kyfw.12306.cn/otn/leftTicket/query'
        request_params = {
            'leftTicketDTO.train_date': train_date,
            'leftTicketDTO.from_station': from_station_en,
            'leftTicketDTO.to_station': dest_station_en,
            'purpose_codes': 'ADULT'
        }
        response = requests.get(api, params=request_params, cookies=self.cookies)

        if response.ok:
            result_table = PrettyTable()
            try:
                response.json()
            except JSONDecodeError:
                print(colortext.light_red('[ERROR] JSON解析异常，可能是旧的请求API发生变化\n%s' % api))
                sys.exit()
            train_list = response.json().get('data').get('result')
            print(colortext.light_green('\n车次及余票信息查询成功，正在查询票价数据...\n'))
            result_table.field_names = ['车次', '车站', '时间', '历时', '商务座/特等座', '一等座', '二等座', '软卧', '硬卧', '硬座', '站票']

            # 遍历查询到的全部车次信息
            satisfied_train_count = 0
            for train in train_list:
                '''
                按 12306 现有的接口，返回的数据是一个列表，单条数据是以 | 分隔的字符串
                在分析这里的数据时，我是靠规律和基本猜测确定对应数据在哪个字段上的
                不知道官方接口为什么要这样返回数据，防止爬虫？感觉这样也防不住啊！
                '''
                train_info = train.split('|')
                train_number, station, train_time, duration = self._format_train_info_fields(train_info)

                # 根据输入参数过滤列车类型
                current_train_type = '-' + train_number[0].lower()
                if not need_filter or self.args[current_train_type] is True:
                    satisfied_train_count += 1
                    # 余票及对应票价
                    tickets_and_prices = self._query_train_tickets_and_prices(train_info, train_date)
                    result_table.add_row([
                        train_number, station, train_time, duration, tickets_and_prices['swz'],
                        tickets_and_prices['ydz'], tickets_and_prices['edz'], tickets_and_prices['rw'],
                        tickets_and_prices['yw'], tickets_and_prices['yz'], tickets_and_prices['wz']
                    ])

            # 打印数据结果
            train_date = colortext.light_yellow(train_date)
            from_city = colortext.light_green(self.db.select_station_name_cn(from_city))
            dest_city = colortext.light_red(self.db.select_station_name_cn(dest_city))
            train_count = colortext.light_blue(satisfied_train_count)
            print('\n查询到满足条件的 %s 从 %s 到 %s 的列车一共 %s 趟\n' % (train_date, from_city, dest_city, train_count))
            print(result_table)

    def _format_train_info_fields(self, train_info):
        # 车次
        train_number = train_info[3]
        # 出发车站
        from_station_cn = colortext.light_green(self.db.select_station_name_cn(train_info[6]))
        # 到达车站
        dest_station_cn = colortext.light_red(self.db.select_station_name_cn(train_info[7]))
        station = from_station_cn + '\n' + dest_station_cn
        # 发车时间
        from_time = colortext.light_green(train_info[8])
        # 到达时间
        dest_time = colortext.light_red(train_info[9])
        train_time = from_time + '\n' + dest_time
        # 历时多久
        duration = train_info[10]

        return train_number, station, train_time, duration

    def _query_train_tickets_and_prices(self, train_info, train_date):
        """整理余票数据，查询各个坐席的票价"""

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
        response = requests.get(api, params=request_params, cookies=self.cookies)

        tickets_and_prices = {
            'swz': train_info[32] or self.unsupported_seat,  # 商务座/特等座余票
            'ydz': train_info[31] or self.unsupported_seat,  # 一等座余票
            'edz': train_info[30] or self.unsupported_seat,  # 二等座余票
            'rw': train_info[23] or self.unsupported_seat,  # 软卧余票
            'yw': train_info[28] or self.unsupported_seat,  # 硬卧余票
            'yz': train_info[29] or self.unsupported_seat,  # 硬座余票
            'wz': train_info[26] or self.unsupported_seat  # 站票余票
        }

        if response.ok:
            '''
            通过测试和观察，查询车票请求频率过快时会大概率导致请求失败，从而得到错误页面而不是正确的响应
            所以此处暂时以简单的方式做一个请求频率限制，每请求成功一次睡眠几秒钟，以此来规避请求异常问题
            '''
            print('编号为 %s 的列车票价请求成功，%d 秒后执行下一次车票查询请求' % (train_uuid, self.request_interval_seconds))
            time.sleep(self.request_interval_seconds)
            price_info = response.json().get('data')
            tickets_and_prices['swz'] += '\n' + colortext.light_yellow(price_info.get('A9', ''))
            tickets_and_prices['ydz'] += '\n' + colortext.light_yellow(price_info.get('M', ''))
            tickets_and_prices['edz'] += '\n' + colortext.light_yellow(price_info.get('O', ''))
            tickets_and_prices['rw'] += '\n' + colortext.light_yellow(price_info.get('A4', ''))
            tickets_and_prices['yw'] += '\n' + colortext.light_yellow(price_info.get('A3', ''))
            tickets_and_prices['yz'] += '\n' + colortext.light_yellow(price_info.get('A1', ''))
            # 站票票价先匹配普通列车，等于硬座票价，如果匹配不到，那么就等于二等座的票价
            tickets_and_prices['wz'] += '\n' + colortext.light_yellow(price_info.get('A1', price_info.get('WZ', '')))

        return tickets_and_prices

    def _check_input_args(self):
        """检查输入参数"""
        from_city = self.args['<from_city>']
        dest_city = self.args['<dest_city>']

        # 检查输入的城市名是否正确
        from_station_en = self.db.select_station_name_en(from_city)
        if from_station_en is None:
            print(colortext.light_red('\n参数错误：出发城市 [%s] 不是一个正确的城市名' % from_city))
            sys.exit(1)

        dest_station_en = self.db.select_station_name_en(dest_city)
        if dest_station_en is None:
            print(colortext.light_red('\n参数错误：到达城市 [%s] 不是一个正确的城市名' % dest_city))
            sys.exit(1)

        # 检查输入的乘车日期是否正确
        train_date = self.args['<date>']
        today_date_str = str(date.today())
        train_date = train_date or today_date_str
        is_date = re.match(r'^(2\d{3}-\d{2}-\d{2})$', train_date)
        train_date_ymd = train_date.split('-')
        if not is_date or int(train_date_ymd[1]) > 12 or int(train_date_ymd[2]) > 31 or train_date < today_date_str:
            print(colortext.light_yellow('\n参数错误：乘车日期 [%s] 不正确，将自动查询今天的车次信息' % train_date))
            train_date = today_date_str

        # 判断是否需要执行列车类型过滤操作
        need_filter = 0
        for train_type in ['-g', '-c', '-d', '-k', '-t', '-z', '-l']:
            if self.args[train_type] is True:
                need_filter += 1

        return from_city, dest_city, from_station_en, dest_station_en, train_date, need_filter


if __name__ == '__main__':
    app = TrainTicketsFinder()
    app.query_satisfied_trains_info()
