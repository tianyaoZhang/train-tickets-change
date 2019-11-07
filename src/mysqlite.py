#!/usr/bin/env python3
"""将核心数据使用 sqlite 做本地存储，封装一些数据操作方法，在主程序中以模块的方式来调用"""

import os
import sqlite3

import colortext


class Sqlite:

    COMMA = ','

    def __init__(self, dbname):
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.connect = sqlite3.connect(os.path.join(app_root, dbname))
        self.cursor = self.connect.cursor()
        self.table_name_station = 'station'
        self.create_table_station()

    def create_table_station(self):
        sql = '''
            CREATE TABLE IF NOT EXISTS %s (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_cn VARCHAR(5) NOT NULL,
                name_en CHAR(3) NOT NULL,
                name_pinyin VARCHAR(16) NOT NULL,
                name_pinyin_short VARCHAR(5) NOT NULL
            )
        ''' % self.table_name_station
        self._create_table(sql)

    def batch_insert_stations_data(self, stations_data):
        for i, station in enumerate(stations_data):
            stations_data[i] = str(station)
        sql = 'INSERT INTO %s (name_cn, name_en, name_pinyin, name_pinyin_short) VALUES' % self.table_name_station
        sql += Sqlite.COMMA.join(stations_data)
        try:
            self.cursor.execute(sql)
            self.connect.commit()
        except Exception as error:
            print(colortext.light_red('批量插入车站数据错误，发生异常：%s' % error))
            self.connect.rollback()
            self.connect.close()

    def select_station_name_en(self, input_station_name):
        sql = 'SELECT name_en FROM %s WHERE name_cn = "%s" OR name_pinyin = "%s"' % (
            self.table_name_station, input_station_name, input_station_name
        )
        try:
            self.cursor.execute(sql)
            result = self.cursor.fetchone()
            return result and result[0]
        except Exception as error:
            print(colortext.light_red('数据查询失败：%s\n发生异常：%s' % (sql, error)))
            self.connect.close()

    def select_station_name_cn(self, input_station_name):
        sql = 'SELECT name_cn FROM %s WHERE name_en = "%s" OR name_pinyin = "%s"' % (
            self.table_name_station, input_station_name, input_station_name
        )
        try:
            self.cursor.execute(sql)
            result = self.cursor.fetchone()
            return result and result[0]
        except Exception as error:
            print(colortext.light_red('数据查询失败：%s\n发生异常：%s' % (sql, error)))
            self.connect.close()

    def select_one_from(self, table_name):
        sql = 'SELECT * FROM %s' % table_name
        try:
            self.cursor.execute(sql)
            return self.cursor.fetchone()
        except Exception as error:
            print(colortext.light_red('数据查询失败：%s\n发生异常：%s' % (sql, error)))
            self.connect.close()

    def _create_table(self, create_table_sql):
        try:
            self.cursor.execute(create_table_sql)
            self.connect.commit()
        except Exception as error:
            print(colortext.light_red('数据表创建失败：%s\n发生异常：%s' % (create_table_sql, error)))
            self.connect.rollback()
            self.connect.close()
