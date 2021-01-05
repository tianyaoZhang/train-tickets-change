#!/usr/bin/env python3
"""
基于 Python 3.x 的命令行版 12306 火车票查询器

Usage:
    app.py (<from_city>) [<inte_city>] (<dest_city>) [<date>] [-g][-c][-d][-k][-t][-z][-l]
"""

import re
import sys
import time
from datetime import date, datetime, timedelta
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
        self.request_interval_seconds = 1
        # 不支持的坐席类别用下面的符号表示
        self.unsupported_seat = ""# colortext.light_yellow('×')
        # 初始化数据库并创建数据表
        self.db = Sqlite('data.sqlite3')
        # 获取并加载全国火车站站名信息
        self.fetch_all_station_names()
        # 尝试获取 12306 网站 cookie
        self.cookies = requests.get('https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc').cookies
        self.tickets_api = 'https://kyfw.12306.cn/otn/leftTicket/queryT'

    def fetch_all_station_names(self):
        """获取全国火车站站名信息，在 12306 网站上是以下面的 JavaScript 链接直接写死了返回来的"""
        # if self.db.select_one_from(self.db.table_name_station) is None:
        response = requests.get('https://kyfw.12306.cn/otn/resources/js/framework/station_name.js?station_version=1.9181')
        # response = requests.get('https://www.12306.cn/index/script/core/common/station_name_v10115.js')
        response.encoding = self.response_encoding
        if response.ok:
            stations = re.findall(r'([\u4e00-\u9fa5]+)\|([A-Z]+)\|([a-z]+)\|([a-z]+)', response.text)
            self.db.batch_insert_stations_data(stations)

    def _get_station_name(self,city):
        station_en = self.db.select_station_name_en(city)
        if station_en is None:
            station_cn = self.db.select_station_name_cn(city)
            if station_cn is None:
                print(colortext.light_red('\n参数错误：出发城市 [%s] 不是一个正确的城市名' % city))
                sys.exit(1)
            return station_cn,city
        return city, station_en

    def query_train_time_tickets(self, from_city, dest_city, train_date):
        """
            返回两站之间火车信息
        """
        trains = []

        f_station_cn,f_station_en = self._get_station_name(from_city)
        d_station_cn,d_station_en = self._get_station_name(dest_city)

        # 检查输入的乘车日期是否正确
        today_date_str = str(date.today())
        train_date = train_date or today_date_str
        is_date = re.match(r'^(2\d{3}-\d{2}-\d{2})$', train_date)
        train_date_ymd = train_date.split('-')
        if not is_date or int(train_date_ymd[1]) > 12 or int(train_date_ymd[2]) > 31 or train_date < today_date_str:
            print(colortext.light_yellow('\n参数错误：乘车日期 [%s] 不正确，将自动查询今天的车次信息' % train_date))
            train_date = today_date_str
        api = self.tickets_api
        request_params = {
            'leftTicketDTO.train_date': train_date,
            'leftTicketDTO.from_station': f_station_en,
            'leftTicketDTO.to_station': d_station_en,
            'purpose_codes': 'ADULT'
        }
        try:
            response = requests.get(api, params=request_params, cookies=self.cookies)
            if (not response.ok) or response.status_code != 200:
                print("没有得到信息--zty")
                sys.exit()
            response_json = response.json()
            train_list = response_json.get('data').get('result')
            print(colortext.light_green('\n车次及余票信息查询成功，正在查询票价数据...\n'))
        except JSONDecodeError:
            print(colortext.light_red('[ERROR] JSON解析异常，可能是旧的请求API发生变化\n%s' % api))

        for idx, train in enumerate(train_list):
            '''
            按 12306 现有的接口，返回的数据是一个列表，单条数据是以 | 分隔的字符串
            在分析这里的数据时，我是靠规律和基本猜测确定对应数据在哪个字段上的
            不知道官方接口为什么要这样返回数据，防止爬虫？感觉这样也防不住啊！
            '''
            # print(f"find {idx}/{len(train_list)}")
            train_info = train.split('|')

            tickets_remain = {
                'swz': train_info[32] or self.unsupported_seat,  # 商务座/特等座余票
                'ydz': train_info[31] or self.unsupported_seat,  # 一等座余票
                'edz': train_info[30] or self.unsupported_seat,  # 二等座余票
                'rw': train_info[23] or self.unsupported_seat,  # 软卧余票
                'yw': train_info[28] or self.unsupported_seat,  # 硬卧余票
                'yz': train_info[29] or self.unsupported_seat,  # 硬座余票
                'wz': train_info[26] or self.unsupported_seat  # 站票余票
            }
            go_flag= False
            if train_info[1] == '列车停运':
                print(f' [{train_info[3]}] 在[{train_date}] 停运')
                continue
            for item in tickets_remain.values():
                if "有" in item:
                    go_flag = True
                    break
                if bool(re.search(r'\d',item)):
                    go_flag = True
                    break
            if go_flag:
                duration=timedelta(hours=int(train_info[10].split(":")[0]),minutes=int(train_info[10].split(":")[1]))
                from_time = datetime.strptime(train_date+"-"+train_info[8],"%Y-%m-%d-%H:%M")
                start_station,start_station_e = self._get_station_name(train_info[4])
                end_station, end_station_e = self._get_station_name(train_info[5])
                from_station,from_station_e  = self._get_station_name(train_info[6])
                dest_station, dest_station_e = self._get_station_name(train_info[7])

                trains.append({
                    "train_number" :train_info[3],

                    "start_station_e": start_station_e,
                    "start_station":start_station,
                    "end_station": end_station,
                    "end_station_e":end_station_e,
                    "from_station":from_station,
                    "from_station_e" : from_station_e,
                    # 到达车站
                    "dest_station":dest_station,
                    "dest_station_e" : dest_station_e,
                    # 发车时间
                    "from_time" : from_time,
                    # 到达时间
                    "dest_time" : from_time+duration,
                    "dest_time_check":train_info[9],
                    "duration" : duration,

                    "tickets_remain" : tickets_remain,

                    "train_uuid" : train_info[2],
                    "from_station_no" : train_info[16],
                    "to_station_no" : train_info[17],
                    "seat_types" : train_info[35]
                })
        print(f"从{f_station_cn}到{d_station_cn}共 {len(trains)}/{len(train_list)}趟列车")
        return len(trains),len(train_list),trains



    def query_satisfied_trains_info(self):
        """
        查询满足条件的车票信息，接口需要传递四个参数
        leftTicketDTO.train_date - 乘车日期，例如：2019-10-24，我这里做了一点优化处理，如果命令行不输日期参数，就默认查询当天
        leftTicketDTO.from_station - 出发车站，需要传车站的站名英文简写，我这里做了一点简化，只传出发的城市名称，接口也能够正确查询出车票信息
        leftTicketDTO.to_station - 到达车站，同出发车站做了一样的处理
        purpose_codes - 普通票或学生票，普通票传值为 ADULT
        """
        from_city, _, dest_city, from_station_en,_, dest_station_en, train_date, need_filter = self._check_input_args()
        api = self.tickets_api
        request_params = {
            'leftTicketDTO.train_date': train_date,
            'leftTicketDTO.from_station': from_station_en,
            'leftTicketDTO.to_station': dest_station_en,
            'purpose_codes': 'ADULT'
        }
        response = requests.get(api, params=request_params, cookies=self.cookies)

        if response.ok:
            if response.status_code!=200:
                print("没有得到信息--zty")
                sys.exit()
            try:
                response_json = response.json()
                train_list = response_json.get('data').get('result')
                print(colortext.light_green('\n车次及余票信息查询成功，正在查询票价数据...\n'))
            except JSONDecodeError:
                print(colortext.light_red('[ERROR] JSON解析异常，可能是旧的请求API发生变化\n%s' % api))
                sys.exit()

            result_table = PrettyTable()
            table_header = ['车次', '车站', '时间', '历时', '商务座/特等座', '一等座', '二等座', '软卧', '硬卧', '硬座', '站票']
            result_table.field_names = table_header

            # 遍历查询到的全部车次信息
            satisfied_train_count = 0
            for idx,train in enumerate(train_list):
                '''
                按 12306 现有的接口，返回的数据是一个列表，单条数据是以 | 分隔的字符串
                在分析这里的数据时，我是靠规律和基本猜测确定对应数据在哪个字段上的
                不知道官方接口为什么要这样返回数据，防止爬虫？感觉这样也防不住啊！
                '''
                print(f"find {idx}/{len(train_list)}")
                train_info = train.split('|')
                train_number, station, train_time, duration = self._format_train_info_fields(train_info)

                # 根据输入参数过滤列车类型
                current_train_type = '-' + train_number[0].lower()
                if not need_filter or self.args[current_train_type] is True:
                    # 跳过【停运列车】的数据查询
                    if train_info[1] != '列车停运':
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
            from_city = colortext.light_green(self.db.select_station_name_cn(from_station_en))
            dest_city = colortext.light_red(self.db.select_station_name_cn(dest_station_en))
            train_count = colortext.light_blue(satisfied_train_count)
            print('\n查询到满足条件的 %s 从 %s 到 %s 的列车一共 %s 趟（已过滤掉停运列车数据）\n' % (
                train_date, from_city, dest_city, train_count
            ))
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

        # if response.ok:
        #     '''
        #     通过测试和观察，查询车票请求频率过快时会大概率导致请求失败，从而得到错误页面而不是正确的响应
        #     所以此处暂时以简单的方式做一个请求频率限制，每请求成功一次睡眠几秒钟，以此来规避请求异常问题
        #     '''
        #     if response.status_code!=200:
        #         print("没有得到价格--zty")
        #         sys.exit()
        #
            # time.sleep(self.request_interval_seconds)
        request_interval_seconds = 0
        while (True):
            try:
                response = requests.get(api, params=request_params, cookies=self.cookies)
                if (not response.ok) or response.status_code != 200:
                    print("没有得到价格--zty")
                    break
                    # sys.exit()
                time.sleep(request_interval_seconds if request_interval_seconds > 1 else 0)
                response_json = response.json()
                price_info = response_json.get('data')
                print('编号为 %s 的列车票价请求成功' % (train_info[3]))
                break
            except JSONDecodeError:
                print(colortext.light_red(f'[ERROR] {train_info[3]}  JSON解析异常，可能是请求参数异常\n{request_params} ，'
                                          f'{ request_interval_seconds} 秒后执行下一次车票查询请求'))

                request_interval_seconds +=1


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
        internal_city = self.args['<inte_city>']
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

        internal_station_en = self.db.select_station_name_en(internal_city)
        if internal_station_en is None:
            print(colortext.light_red('\n参数错误：到达城市 [%s] 不是一个正确的城市名' % internal_city))
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

        return from_city,internal_city, dest_city, from_station_en, internal_station_en,dest_station_en, train_date, need_filter

    def show_rounte(self,train):
        seat = colortext.light_blue(train['tickets_remain']['edz']) if \
            train['tickets_remain']['edz'] else train['tickets_remain']['yz']
        str = ""
        str += f"[{colortext.light_red(train['train_number'])}]({seat})"
        # str += f"({train['start_station']}-{train['end_station']})"
        str += f"\t{train['from_station']}  \t{train['from_time'].strftime('%m-%d %H:%M')}"
        str += f"-->\t{train['dest_station']} {train['dest_time'].strftime('%m-%d %H:%M')}"
        return str
    def calculte_timedelta(self,first,second):
        minutes = (second-first).seconds/60
        hours = minutes // 60 + 24*(second-first).days
        minutes = minutes % 60
        return int(hours),int(minutes)

    def change(self,source,internalcity,destination,train_date,same_inter=True):

        _, _, trains_d = app.query_train_time_tickets(from_city=internalcity, dest_city=destination, train_date=train_date)
        _, _, trains_f = app.query_train_time_tickets(from_city=source, dest_city=internalcity, train_date=train_date)
        trains_f.sort(key=lambda tr: tr["dest_time"])
        trains_d.sort(key=lambda tr: tr["from_time"])
        train_pairs = []
        for tf in trains_f:
            for td in trains_d:
                if tf["dest_time"] > td["from_time"]:
                    continue
                train_pairs.append((tf, td))
        # print(train_pairs)
        num = 0
        final_results = []
        for first, second in train_pairs:
            if same_inter and first["dest_station"] != second["from_station"]:
                continue
            str = app.show_rounte(first)
            str2 = app.show_rounte(second)
            totalhours, totalminutes = app.calculte_timedelta(first["from_time"], second['dest_time'])
            hours, minutes = app.calculte_timedelta(first["dest_time"], second['from_time'])
            totaltime = colortext.light_green(f"[total {totalhours}:{totalminutes}]")
            changetime = colortext.light_yellow(f"@({hours}:{minutes})")
            final_results.append({
                "str": f"{totaltime}  \t{str}  \t{changetime}\t{str2}",
                "total": timedelta(hours=totalhours, minutes=totalminutes),
                "change": timedelta(hours=hours, minutes=minutes)
            })
            # print( f"{totaltime}  \t{str}  \t{changetime}\t{str2}")
            # num+=1
        final_results.sort(key=lambda x: x["total"])
        # final_results.sort(key=lambda x:x["change"])
        for item in final_results:
            print(item["str"])
        print(f"总共有 {len(final_results)}/{len(train_pairs)}种方法")


if __name__ == '__main__':
    app = TrainTicketsFinder()
    # app.query_satisfied_trains_info()
    train_date = "2021-01-05"
    # app.change("北京","呼和浩特东","鄂尔多斯","2021-01-16")
    app.change("EEC","包头","北京","2021-01-16")

